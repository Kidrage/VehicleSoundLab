"""Audit the actual V0.7 artifacts and retain the full goal's open requirements."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from runtime_review import ROOT,rms
from verify_v06 import audit_preservation
from render_v07_review import traces
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.7.0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def main():
    report=read(OUT/'verification.json');assert report['version']=='0.7.0' and report['seed']==48271
    for name,digest in report['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in report['binaries'].items():assert sha(ROOT/'build-v07/Release'/name)==digest,name
    takes={};trace_rows={}
    for name,case in report['cases'].items():
        gains=[]
        for tag in ['bypass','enabled']:
            item=case[tag]['audition'];path=OUT/item['file'];assert sha(path)==item['sha256']
            x,sr=sf.read(path,always_2d=True);info=sf.info(path)
            assert sr==48000 and info.subtype=='PCM_24' and info.channels==2 and np.isfinite(x).all()
            assert float(abs(x).max())<=.850001 and abs(rms(x)-case[tag]['rms_dbfs']-item['gain_db'])<.001
            gains.append(item['gain_db']);takes[path.name]=dict(sha256=sha(path),rms_dbfs=rms(x),peak=float(abs(x).max()),common_gain_db=item['gain_db'])
        assert gains[0]==gains[1]
        assert (OUT/f'{name}_bypass.wav').read_bytes()==(OUT/f'{name}_v06.wav').read_bytes()
        trace_rows[name]=traces(OUT/f'{name}_v06.csv',OUT/f'{name}_enabled.csv')
    assert len(takes)==10
    for profile in range(5):
        a,b=[OUT/f'compat_profile{profile}_{tag}.wav' for tag in ['v06','v07']]
        assert a.read_bytes()==b.read_bytes() and sha(a)==report['steady_compatibility'][str(profile)]
    tests=ET.parse(OUT/'ctest.xml').getroot();assert tests.attrib['tests']=='9' and tests.attrib['failures']=='0'
    assert {x.attrib['name'] for x in tests.findall('testcase')}=={
        'dsp_invariants','driving_states','state_layer_response','high_order_sources','firing_geometry',
        'independent_clocks','transmission_rev_match','fuel_cut_excitation','spatial_objects'}
    dna=read(OUT/'dna_check/dna_pipeline_check.json')
    assert dna['result']=='pass' and dna['dsp_version']=='0.7.0' and dna['renderer_sha256']==report['binaries']['vsl_render.exe']
    smoke=read(OUT/'ui_smoke.json');assert smoke==report['device'] and smoke['dsp']=='0.7.0'
    for key in ['fuel_controls','fuel_preset_roundtrip','control_isolation','device_stream_muted',
                'waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert smoke[key],key
    assert smoke['queue_empty_observations']==0 and .95<smoke['device_seconds']/smoke['wall_seconds']<1.02
    assert smoke['render_ms_mean']<512/48
    preset=(OUT/'ui_control_roundtrip.ini').read_text();assert 'fuel_cut=0' in preset and 'pumping=0.42' in preset and 'release_time=0.32' in preset
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==10
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V07试听.html').read_text(encoding='utf-8'))
    measurements=read(OUT/'excitation_measurements.json');assert measurements['result']=='pass'
    assert measurements['script_sha256']==sha(ROOT/'tools/analyze_v07_excitation.py')
    for key in ['inputs','plots']:
        for name,digest in measurements[key].items():assert sha(OUT/name)==digest,name
    assert measurements['motored_vs_fired_exhaust_cut_window_db']< -10
    assert len(measurements['dry_non_exhaust_stems_bit_identical'])==8
    observations=read(ROOT/'references/analysis/overrun_v1/results.json')
    assert observations['script_sha256']==sha(ROOT/'tools/analyze_overrun.py')
    for item in observations['recordings']:assert sha(ROOT/item['master'])==item['master_sha256']
    for name,digest in observations['outputs'].items():assert sha(ROOT/'references/analysis/overrun_v1'/name)==digest
    video=observations['video_context'];assert sha(ROOT/video['video'])==video['sha256']
    upstream=observations['upstream'];assert upstream['revision']=='ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
    head=json.loads((ROOT/'research/upstream_head_v07.json').read_text(encoding='utf-8-sig'))
    assert head['sha']==upstream['revision']
    assert sha(ROOT/'research/upstream/gen/v10_powertrain.gendsp')==upstream['gen_sha256']
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js')==upstream['drive_controller_sha256']
    scene=read(OUT/'drive_714_scene.json')
    assert scene['dsp_version']=='0.7.0' and len(scene['objects'])==10 and scene['parameters']['fuel_cut']==1
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path=OUT/obj['file'];info=sf.info(path)
        assert sha(path)==obj['sha256'] and info.channels==1 and info.subtype=='FLOAT' and info.frames==1440000
    with (OUT/'drive_714_v07.wav').open('rb') as file:
        assert file.read(4)==b'RIFF';file.read(4);assert file.read(4)==b'WAVE';chunks={}
        while True:
            name,size=struct.unpack('<4sI',file.read(8))
            if name==b'data':break
            chunks[name]=file.read(size)
            if size%2:file.read(1)
    assert struct.unpack('<HHI',chunks[b'fmt '][:8])==(65534,12,48000)
    assert struct.unpack('<I',chunks[b'fmt '][20:24])[0]==0x2d63f
    preserved=audit_preservation()
    frozen=ROOT/'baselines/v0.6.0';manifest=read(frozen/'manifest.json');assert len(manifest['files'])==161
    for item in manifest['files']:assert sha(frozen/item['path'])==item['sha256'],item['path']
    preserved['frozen_baseline_files_verified']['v0.6.0']=161
    source=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=[ROOT/name for name in ['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V07试听.html','research/V07断油与泵气激励.md','research/upstream_head_v07.json']]
    deliverables += [ROOT/'tools'/name for name in ['render_v07_review.py','analyze_v07_excitation.py','analyze_overrun.py','make_v07_review.py',
        'comparison_page.py','runtime_review.py','verify_v07.py','freeze_v07.py','verify_v06.py','check_dna_pipeline.py','verify_review_player.cjs','capture_preview.py']]
    audit=dict(result='pass',version='0.7.0',ctest_count=9,audition_files=takes,
        bypass_dynamic_scenarios_bit_identical=5,old_vehicle_trace_rows_verified=trace_rows,
        factory_steady_templates_bit_identical=5,excitation=measurements,device=smoke,browser=browser,dna_pipeline=dna,
        spatial=dict(source_objects=10,channels=12,channel_mask='0x2d63f',physical_audition=False),
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(source)},
        deliverables={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(deliverables)},
        analysis=dict(results_sha256=sha(ROOT/'references/analysis/overrun_v1/results.json'),upstream=upstream,current_head_check=head),
        **preserved,limits=report['limits'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    previous=read(ROOT/'research/goal_progress_v06.json');full=previous['full_objective_audit']
    full[1].update(status='Incomplete: fuel-aware fired/motored excitation adds a new sound process. Target-car RPM/load spectra, cycle variability and subjective naturalness remain unproven.',evidence='research/V07试听.html; renders/v0.7.0/workspace_audit.json')
    full[2].update(status='Partial: additional sampled stationary/moving exhaust context and independent band decays recorded. No synchronized pedal, RPM, gear or injector telemetry; ECU thresholds are not video fitted.',evidence='references/analysis/overrun_v1')
    full[4].update(status='Partial: sport shifting/rev match plus fuel-cut eligibility, hysteresis and motored pressure implemented. Physical torque/inertia, measured ECU/pipes, mechanical modes and shutdown calibration remain incomplete.',evidence='src/drive/fueling.c; src/core/excitation.c; tests/test_fueling.c')
    progress=dict(goal_status='active',review_version='0.7.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Independent modular fuel eligibility/hysteresis/dwell/resume and sample-rate fired/motored pressure',
            'Crank-driven pressure into a replaceable cavity, internal-blip refuel and shutdown-from-cut guard',
            'Additional approved reference decay/video observations and exact pinned V6 code evidence',
            'Actual UI control/preset checks; sliders update only the touched parameter, preserving exact stored values',
            'Five shared-gain comparison pairs, actual dry-stem ablations and 7.1.4/source export',
            'Nine CTests, DNA interchange, muted device timing, native/browser UI; six old baselines and source media preserved'],
        evidence=dict(review='research/V07试听.html',implementation='research/V07断油与泵气激励.md',audit='renders/v0.7.0/workspace_audit.json'),
        full_objective_audit=full,
        remaining_work=['Subjective assessment and Lamborghini RPM/load/state spectral calibration with held-out passages',
            'Replace free-running mechanical tones with driven structural modes; improve cycle variation and intake/exhaust transfer',
            'Strengthen synchronized video/event telemetry, torque/inertia and shutdown/starting models',
            'Calibrate separate engine/air/road/room sources and validate actual stereo and future 7.1.4 hardware',
            'Keep broad objective active; numerical mechanism checks do not prove perceptual realism'])
    (ROOT/'research/goal_progress_v07.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',ctest_count=9,common_gain_pairs=5,exhaust_cut_db=measurements['motored_vs_fired_exhaust_cut_window_db'],
        frozen=preserved['frozen_baseline_files_verified'],device=smoke),indent=2))


if __name__=='__main__':main()
