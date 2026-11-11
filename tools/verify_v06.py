"""Audit the V0.6 exports, geometry, source ledger and preserved baselines."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'renders/v0.6.0'
ANALYSIS = ROOT / 'references/analysis/bank_geometry_v1'
sys.path.insert(0, str(ROOT / 'tools/python_deps'))
import numpy as np
import soundfile as sf


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit_audio(report):
    takes = {}
    traces = {}
    assert len(report['cases']) == 10
    for name, case in report['cases'].items():
        for tag in ['v05', 'v06']:
            item = case[tag]['audition']
            file = OUT / item['file']
            assert sha(file) == item['sha256'], file
            x, sr = sf.read(file, always_2d=True)
            info = sf.info(file)
            assert sr == 48000 and info.channels == 2 and info.subtype == 'PCM_24'
            assert np.isfinite(x).all() and abs(x).max() <= .850001
            measured = float(10 * np.log10(np.mean(x*x)))
            assert abs(measured - case[tag]['rms_dbfs'] - item['gain_db']) < .001
            if name == 'pure5000_mono':
                assert np.array_equal(x[:, 0], x[:, 1])
            takes[item['file']] = dict(sha256=sha(file), frames=len(x),
                subtype=info.subtype, channels=2, rms_dbfs=measured,
                peak=float(abs(x).max()), explicit_gain_db=item['gain_db'])
        if name != 'pure5000_mono':
            a, b = [OUT / f'{name}_{tag}.csv' for tag in ['v05', 'v06']]
            assert a.read_bytes() == b.read_bytes(), name
            traces[name] = sha(a)
    assert len(traces) == 9 and len(takes) == 20
    for profile in range(1, 5):
        a, b = [OUT / f'compat_profile{profile}_{tag}.wav' for tag in ['v05', 'v06']]
        assert a.read_bytes() == b.read_bytes()
        assert sha(a) == report['other_templates'][str(profile)]['sha256']
    assert (OUT/'custom_pure_v05.wav').read_bytes() == (OUT/'custom_pure_v06.wav').read_bytes()
    return dict(audition_files=takes, identical_driver_trace_sha256=traces,
                other_templates_bit_identical=4, imported_pure_dna_bit_identical=True)


def audit_exported_phase():
    """Measure the actual pre-spatial stems, including active high orders."""
    orders = np.array([1,2,3,4,5,10,15,20,28,29,30,31,35,40,45])
    start, stop, sr = 144000, 264000, 48000
    t = np.arange(start, stop) / sr
    frequencies = 5000*10/240*orders
    window = np.hanning(len(t))
    projection = window[:, None]*np.exp(-2j*np.pi*t[:, None]*frequencies)
    results = {}
    for tag, offset in [('v05', .5), ('v06', .625)]:
        phases = []
        amplitudes = []
        paths = [OUT/f'stems/pure5000_{tag}_exhaust_{side}.wav' for side in ['left','right']]
        for path in paths:
            x, sample_rate = sf.read(path)
            info = sf.info(path)
            assert sample_rate == sr and info.subtype == 'FLOAT' and info.channels == 1
            z = x[start:stop] @ projection
            phases.append(np.angle(z))
            amplitudes.append(2*abs(z)/window.sum())
        expected = -2*np.pi*orders*offset - 2*np.pi*frequencies*.00038
        error = np.angle(np.exp(1j*(phases[1]-phases[0]-expected)))
        assert min(amplitudes[0]) > .001
        assert max(abs(error)) < .0001, tag
        results[tag] = dict(bank_period_offset=offset, orders=orders.tolist(),
            left_amplitudes=amplitudes[0].tolist(), phase_error_rad=error.tolist(),
            max_phase_error_rad=float(max(abs(error))),
            stems_sha256={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in paths})
    return dict(window_file_seconds=[start/sr, stop/sr], fixed_rpm=5000,
        bank_frequency_hz=5000*10/240, unmeasured_propagation_delay_seconds=.00038,
        results=results, scope='Rendered phase consistency only; not measured target-car phase or realism.')


def audit_runtime(report):
    tests = ET.parse(OUT/'ctest.xml').getroot()
    assert tests.attrib['tests'] == '8' and tests.attrib['failures'] == '0'
    assert {x.attrib['name'] for x in tests.findall('testcase')} == {
        'dsp_invariants','driving_states','state_layer_response','high_order_sources',
        'firing_geometry','independent_clocks','transmission_rev_match','spatial_objects'}
    dna = read(OUT/'dna_check/dna_pipeline_check.json')
    assert dna['result'] == 'pass' and dna['dsp_version'] == '0.6.0'
    assert dna['renderer_sha256'] == sha(ROOT/'build-v06/Release/vsl_render.exe')
    smoke = read(OUT/'ui_smoke.json')
    assert smoke == report['device'] and smoke['dsp'] == '0.6.0'
    for key in ['device_stream_muted','waveOut_opened_and_queued_audio','export_succeeded',
                'running_latch','manual_shift','shutdown_to_off']:
        assert smoke[key], key
    assert smoke['queue_empty_observations'] == 0
    assert .95 < smoke['device_seconds']/smoke['wall_seconds'] < 1.02
    assert smoke['render_ms_mean'] < smoke['block_frames']/48
    browser = read(OUT/'browser_qa.json')
    assert browser['result'] == 'pass' and browser['metadata_loads'] == 20
    assert browser['reference_metadata_loads'] == 1
    assert browser['reference_playback_mutual_exclusion']
    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):
                    assert (ROOT/'research'/value).resolve().is_file(), value
    Links().feed((ROOT/'research/V06试听.html').read_text(encoding='utf-8'))
    return dict(ctest_count=8, dna_pipeline=dna, device=smoke, browser=browser)


def audit_spatial():
    scene = read(OUT/'drive_714_scene.json')
    assert scene['dsp_version'] == '0.6.0' and len(scene['objects']) == 10
    assert scene['channels'] == ['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path = OUT/obj['file']
        info = sf.info(path)
        assert info.samplerate == 48000 and info.channels == 1 and info.subtype == 'FLOAT'
        assert info.frames == 30*48000 and sha(path) == obj['sha256']
    with (OUT/'drive_714_v06.wav').open('rb') as file:
        assert file.read(4) == b'RIFF'
        file.read(4)
        assert file.read(4) == b'WAVE'
        chunks = {}
        while True:
            name, size = struct.unpack('<4sI', file.read(8))
            if name == b'data':
                break
            chunks[name] = file.read(size)
            if size % 2:
                file.read(1)
    assert struct.unpack('<HHI', chunks[b'fmt '][:8]) == (65534,12,48000)
    assert struct.unpack('<I', chunks[b'fmt '][20:24])[0] == 0x2d63f
    assert struct.unpack('<I', chunks[b'fact'][:4])[0] == 30*48000
    return dict(source_stems=10, format='float32 WAVE 7.1.4 speaker bed',
                channel_mask='0x2d63f', scene_sha256=sha(OUT/'drive_714_scene.json'))


def audit_preservation():
    frozen = {}
    for version, count in [('v0.1.0',23),('v0.2.0',64),('v0.3.0',81),('v0.4.0',99),('v0.5.0',112)]:
        folder = ROOT/'baselines'/version
        manifest = read(folder/'manifest.json')
        assert len(manifest['files']) == count
        for item in manifest['files']:
            assert sha(folder/item['path']) == item['sha256'], (version,item['path'])
        frozen[version] = count
    masters = read(ROOT/'references/analysis/joint_stereo_v1/results.json')
    media = {}
    for identity, item in masters['sources'].items():
        path = ROOT/item['master']
        assert sha(path) == item['sha256'] and sf.info(path).subtype == 'FLOAT'
        media[identity+'_master'] = item['sha256']
    assert sf.info(ROOT/'references/clean/B_decoded_float.wav').channels == 2
    for identity in ['A','B']:
        item = read(ROOT/f'references/raw/{identity}_provenance.json')
        assert sha(ROOT/'references/raw'/item['original_file']) == item['sha256']
        media[identity+'_raw'] = item['sha256']
    clip = read(ROOT/'references/clean/A_idle_context_v02.wav.provenance.json')
    assert sha(ROOT/'references/clean/A_idle_context_v02.wav') == clip['output_sha256']
    assert not clip['normalization'] and not clip['denoise'] and clip['channels'] == 'preserved'
    snapshot = read(ROOT/'references/analysis/joint_stereo_v1/review_manifest.json')
    for item in snapshot['files']:
        assert sha(ROOT/item['path']) == item['sha256'], item['path']
    return dict(frozen_baseline_files_verified=frozen, approved_media_sha256=media,
        reference_clip_provenance=clip, preceding_research_snapshot_files_verified=len(snapshot['files']))


def audit_analysis():
    ledger = read(ANALYSIS/'technical_evidence.json')
    for item in [*ledger['primary'], ledger['target_link'], ledger['rejected_number']]:
        assert sha(ROOT/item['local_html']) == item['sha256']
    for item in ledger['primary']:
        assert '54' in item['exact_excerpt'] and '90' in item['exact_excerpt']
    results = read(ANALYSIS/'results.json')
    assert results['script_sha256'] == sha(ROOT/'tools/analyze_bank_geometry.py')
    video = results['video_context']
    assert sha(ROOT/video['video']) == video['sha256']
    return dict(technical_html_files=4, technical_evidence_sha256=sha(ANALYSIS/'technical_evidence.json'),
        source_video_sha256=video['sha256'],
        artifacts={str(p.relative_to(ROOT)).replace('\\','/'):sha(p)
                   for p in sorted(ANALYSIS.iterdir()) if p.is_file()})


def write_progress():
    previous = read(ROOT/'research/goal_progress_v05.json')
    full = previous['full_objective_audit']
    full[1].update(status='Incomplete: V0.6 specializes 5.2 common-pin firing and verifies actual stem phase. Target-car spectra, naturalness and load/state calibration remain unproven.',
        evidence='renders/v0.6.0/workspace_audit.json; research/V06试听.html')
    full[2].update(status='Partial: primary engine-family geometry and additional sampled rear-exterior context checked. No precise RPM, pedal, load, gear or complete event telemetry established.',
        evidence='references/analysis/bank_geometry_v1; research/state_evidence_v02.json')
    progress = dict(goal_status='active', review_version='0.6.0',
        previous_goal_turn_classification='progress', this_goal_turn_classification='progress',
        implemented_this_iteration=[
            'Primary 54/90-degree common-pin evidence, secondary target link and conflicting-number ledger',
            'Independent firing profile consumed by low-order DNA, high orders and NVH pulses',
            'Actual low/high exported stem phase verification and nine identical driver trace pairs',
            'Ten RMS-labelled comparison pairs, approved reference and exclusive-player controls',
            'Eight CTests, DNA interchange, muted device timing, browser/native UI and 7.1.4 export checks',
            'Five prior baselines, approved media and joint-stereo research snapshot verified intact'],
        evidence=dict(implementation='research/V06点火几何与素材核查.md',
            review='research/V06试听.html',audit='renders/v0.6.0/workspace_audit.json'),
        full_objective_audit=full,
        remaining_work=[
            'Subjectively assess V0.6; calibrate RPM/load/state spectra without claiming uncertain source RPM',
            'Establish stronger event/video labels and independent held-out generation checks',
            'Develop fuel cut/residual excitation, physical torque/inertia, mechanical/intake/pipe transfer and cycle variation',
            'Separate engine/air/road/room contributions and validate actual stereo and future 7.1.4 hardware',
            'The broad driving-sound objective remains active; a frozen review is progress, not completion'])
    (ROOT/'research/goal_progress_v06.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')


def main():
    report = read(OUT/'verification.json')
    assert report['version'] == '0.6.0' and report['seed'] == 48271
    for name, digest in report['files'].items():
        assert sha(OUT/name) == digest, name
    code = [ROOT/'CMakeLists.txt', *(ROOT/'src').rglob('*.c'),
            *(ROOT/'src').rglob('*.h'), *(ROOT/'tests').glob('*.c')]
    audit = dict(result='pass', version='0.6.0', **audit_audio(report),
        exported_bank_phase=audit_exported_phase(), **audit_runtime(report),
        spatial=audit_spatial(), **audit_preservation(), analysis=audit_analysis(),
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(code)},
        limits=report['limits'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    write_progress()
    print(json.dumps(dict(result='pass', ctest_count=8, paired_scenarios=10,
        identical_traces=9, phase_max_error_rad={k:v['max_phase_error_rad'] for k,v in audit['exported_bank_phase']['results'].items()},
        frozen=audit['frozen_baseline_files_verified']),indent=2))


if __name__ == '__main__':
    main()
