"""Audit sources, frozen runtime and research artifacts; record goal progress."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf

OUT = ROOT/'references/analysis/joint_stereo_v1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    base = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    low = json.loads((OUT/'low_band_extension.json').read_text(encoding='utf-8'))
    bands = json.loads((OUT/'band_accounting.json').read_text(encoding='utf-8'))
    assert low['original_results_sha256'] == bands['input_results_sha256'] == sha(OUT/'results.json')
    for report in [base, low]:
        for file, digest in report['tools'].items():
            assert sha(ROOT/file) == digest, file
    for value in base['sources'].values():
        assert sha(ROOT/value['master']) == value['sha256']
    raw = []
    for identity in ['A', 'B']:
        source = json.loads((ROOT/f'references/raw/{identity}_provenance.json').read_text(encoding='utf-8'))
        file = ROOT/'references/raw'/source['original_file']
        assert sha(file) == source['sha256']
        raw.append(dict(source=identity, file=str(file.relative_to(ROOT)), sha256=source['sha256']))
    desktop = (Path.home() / 'Desktop' / '2023 Lamborghini Huracan Tecnica - POV Canyon Blast (Binaural Audio).mp3')
    assert not desktop.exists()
    baselines = {}
    live = []
    for version in ['v0.1.0', 'v0.2.0', 'v0.3.0']:
        folder = ROOT/'baselines'/version
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['files']:
            assert sha(folder/entry['path']) == entry['sha256'], (version, entry['path'])
            file = entry['path'].replace('\\', '/')
            if version == 'v0.3.0':
                if file.startswith(('src/', 'tests/')) or file == 'CMakeLists.txt':
                    assert sha(ROOT/file) == entry['sha256'], file
                    live.append(file)
                elif file in ['bin/VehicleSoundLab.exe', 'bin/vsl_render.exe']:
                    target = ROOT/'build/Release'/Path(file).name
                    assert sha(target) == entry['sha256']
                    live.append(str(target.relative_to(ROOT)))
        baselines[version] = len(manifest['files'])
    audio = []
    for name, case in base['cases'].items():
        items = dict(case['auditions'], joint64_low28=low['cases'][name]['audition'])
        for method, item in items.items():
            file = ROOT/item['file']
            assert sha(file) == item['sha256']
            info = sf.info(file)
            assert info.samplerate == 48000 and info.channels == 2 and info.subtype == 'PCM_24'
            assert abs(info.duration-(case['source_seconds'][1]-case['source_seconds'][0])) < 1/48000
            samples, sr = sf.read(file, always_2d=True)
            assert np.isfinite(samples).all() and np.max(abs(samples)) < .95
            rms = float(10*np.log10(np.mean(samples[9600:-9600]**2)))
            target = -23+20*np.log10(item['shared_headroom_gain'])
            assert abs(rms-target) < .001
            audio.append(dict(case=name, method=method, file=item['file'],
                sha256=item['sha256'], peak=float(np.max(abs(samples))), stereo_rms_dbfs=rms))
    browser = json.loads((OUT/'browser_qa.json').read_text(encoding='utf-8'))
    assert browser['result'] == 'pass' and browser['metadata_loads'] == 36
    audit = dict(result='pass', raw_sources=raw, masters_unchanged=True,
        desktop_original_absent=True, frozen_baseline_files_verified=baselines,
        current_runtime_matches_v03=True, live_runtime_files_verified=len(live),
        synthetic_controls='Original static/off-bin stereo, AM/FM long/short and low43.37Hz plus L/R swap assertions passed in generating tools.',
        residual_band_crosscheck='All 24 original reconstruction residuals rechecked from PCM24 audition derivatives within 0.002dB.',
        browser=browser, audio=audio,
        scope='Research-only iteration. Existing CTest/device evidence belongs to unchanged V0.3; no new C build or device test is implied.')
    (OUT/'verification.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    previous = json.loads((ROOT/'research/goal_progress_v03.json').read_text(encoding='utf-8'))
    progress = dict(goal_status='active', current_runtime='0.3.0 frozen',
        previous_goal_turn_classification='progress', this_goal_turn_classification='progress',
        implemented_this_iteration=[
            'Modular offline joint L/R oscillator tracker with separate complex amplitudes, centred fractional-frequency estimation and Hann sidelobe guard',
            'Known stationary/anti-phase/one-sided and dynamic AM/FM controls plus low-frequency and L/R-swap checks',
            'Six approved raw-float stereo excerpts and old/new/long/short/low-band ablations; 36 explicitly RMS-labelled audition files',
            'Band accounting separated out-of-band omission from the waveform residual; 28Hz follow-up on the same fixed budget',
            'Local comparison player preserves playback position; real headless browser metadata/playback/mobile checks passed',
            'Raw/master and frozen baseline audit; running C runtime sources, tests and binaries still match V0.3'],
        evidence=dict(analysis='references/analysis/joint_stereo_v1/results.json',
            band_accounting='references/analysis/joint_stereo_v1/band_accounting.json',
            follow_up='references/analysis/joint_stereo_v1/low_band_extension.json',
            verification='references/analysis/joint_stereo_v1/verification.json',
            review='research/立体声OSC试听.html', note='research/立体声OSC核查.md'),
        full_objective_audit=previous['full_objective_audit'],
        remaining_work=[
            'User listening feedback on V0.3 is optional and pending; keep progressing within the approved exterior V10 target',
            'Test frequency-dependent/multiple-window estimation without masking low orders or spending all trajectories on strong lows',
            'Derive general RPM/load/state and channel-transfer parameters with disjoint generation checks; same-excerpt fits do not establish this',
            'Continue precise video/audio event labels, downshift rev matching and drivetrain/NVH/acoustic calibration',
            'Make justified runtime changes as a new version; preserve V0.3 and the independent object stems for future 7.1.4',
            'Do not mark the broad sound/driving goal complete from offline reconstruction or browser/test passes'])
    progress['full_objective_audit'][3] = dict(requirement='Prepare stereo and future 7.1.4 spatial rendering',
        status='Current object/file routing implemented; shared-frequency offline estimator and stereo diagnostics tested. General source/transfer calibration and physical array audition remain incomplete.',
        evidence='tests/test_spatial.c; references/analysis/joint_stereo_v1; research/立体声OSC核查.md')
    (ROOT/'research/goal_progress_stereo_v1.json').write_text(json.dumps(progress, indent=2), encoding='utf-8')
    include = [ROOT/'research/立体声OSC试听.html', ROOT/'research/立体声OSC核查.md',
               ROOT/'research/goal_progress_stereo_v1.json']
    include += list((ROOT/'tools/osc_research').glob('*.py'))
    include += [ROOT/f'tools/{name}' for name in ['analyze_joint_stereo.py', 'finalize_joint_stereo.py',
        'analyze_low_band_osc.py', 'make_joint_stereo_review.py', 'verify_joint_stereo_ui.cjs', 'finalize_stereo_review.py']]
    include += [p for p in OUT.iterdir() if p.is_file() and p.name not in ['review_manifest.json', 'results.partial.json']]
    manifest = dict(schema='vsl.research-snapshot/1', runtime='0.3.0 unchanged',
        scope='Joint stereo offline research; source approval and raw/master digests remain in their provenance ledgers.',
        files=[dict(path=str(p.relative_to(ROOT)).replace('\\', '/'), sha256=sha(p)) for p in sorted(include)])
    (OUT/'review_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(result='pass', frozen_baselines=baselines, live_runtime_files=len(live),
                          verified_auditions=len(audio), research_manifest_files=len(manifest['files'])), indent=2))


if __name__ == '__main__':
    main()
