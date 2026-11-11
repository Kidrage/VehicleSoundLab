"""Inspect delivered V0.4 files, sources and broad-goal evidence boundaries."""
from pathlib import Path
import hashlib
from html.parser import HTMLParser
import json
import struct
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.4.0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    report=json.loads((OUT/'verification.json').read_text())
    assert report['version']=='0.4.0'
    for name,digest in report['files'].items():assert sha(OUT/name)==digest,name
    for name,case in report['cases'].items():
        assert (OUT/f'{name}_v03.csv').read_bytes()==(OUT/f'{name}_v04.csv').read_bytes()
        for version in ['v03','v04']:
            item=case[version]['audition'];path=OUT/item['file']
            assert sha(path)==item['sha256']
            info=sf.info(path);assert info.channels==2 and info.samplerate==48000 and info.subtype=='PCM_24'
            x,_=sf.read(path,always_2d=True)
            expected=case[version]['rms_dbfs']+item['gain_db']
            assert abs(10*np.log10(np.mean(x*x))-expected)<.001
            assert np.isfinite(x).all() and np.max(abs(x))<=.850001
    for profile in ['1','2','3','4']:
        a=OUT/f'compat_profile{profile}_v03.wav';b=OUT/f'compat_profile{profile}_v04.wav'
        assert a.read_bytes()==b.read_bytes() and sha(a)==report['other_templates'][profile]['sha256']
    tests=ET.parse(OUT/'ctest.xml').getroot()
    assert tests.attrib['tests']=='5' and tests.attrib['failures']=='0'
    assert {t.attrib['name'] for t in tests.findall('testcase')}=={
        'dsp_invariants','driving_states','state_layer_response','high_order_sources','spatial_objects'}
    dna=json.loads((OUT/'dna_check/dna_pipeline_check.json').read_text())
    assert dna['result']=='pass' and dna['dsp_version']=='0.4.0'
    assert dna['renderer_sha256']==sha(ROOT/'build-v04/Release/vsl_render.exe')
    smoke=json.loads((OUT/'ui_smoke.json').read_text())
    assert smoke==report['device'] and smoke['dsp']=='0.4.0' and smoke['device_stream_muted']
    assert smoke['queue_empty_observations']==0 and .95<smoke['device_seconds']/smoke['wall_seconds']<1.02
    assert smoke['render_ms_mean']<512/48
    browser=json.loads((OUT/'browser_qa.json').read_text())
    assert browser['result']=='pass' and browser['metadata_loads']==16
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):
                    assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V04试听.html').read_text(encoding='utf-8'))
    scene=json.loads((OUT/'drive_714_scene.json').read_text())
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    assert len(scene['objects'])==10
    for obj in scene['objects']:
        path=OUT/obj['file'];info=sf.info(path)
        assert info.channels==1 and info.subtype=='FLOAT' and info.frames==30*48000
        assert sha(path)==obj['sha256']
    with (OUT/'drive_714_v04.wav').open('rb') as f:
        assert f.read(4)==b'RIFF';f.read(4);assert f.read(4)==b'WAVE'
        chunks={}
        while True:
            name,size=struct.unpack('<4sI',f.read(8))
            if name==b'data':break
            chunks[name]=f.read(size)
            if size%2:f.read(1)
    assert struct.unpack('<HHI',chunks[b'fmt '][:8])==(65534,12,48000)
    assert struct.unpack('<I',chunks[b'fmt '][20:24])[0]==0x2d63f
    assert struct.unpack('<I',chunks[b'fact'][:4])[0]==30*48000
    frozen={}
    for version in ['v0.1.0','v0.2.0','v0.3.0']:
        folder=ROOT/'baselines'/version;manifest=json.loads((folder/'manifest.json').read_text())
        for entry in manifest['files']:assert sha(folder/entry['path'])==entry['sha256'],(version,entry['path'])
        frozen[version]=len(manifest['files'])
    source_report=json.loads((ROOT/'references/analysis/joint_stereo_v1/results.json').read_text())
    for source in source_report['sources'].values():assert sha(ROOT/source['master'])==source['sha256']
    for identity in ['A','B']:
        raw=json.loads((ROOT/f'references/raw/{identity}_provenance.json').read_text())
        assert sha(ROOT/'references/raw'/raw['original_file'])==raw['sha256']
    # The preceding research snapshot remains reproducible even as C evolves.
    snapshot=json.loads((ROOT/'references/analysis/joint_stereo_v1/review_manifest.json').read_text())
    for entry in snapshot['files']:assert sha(ROOT/entry['path'])==entry['sha256'],entry['path']
    multi=json.loads((ROOT/'references/analysis/multires_v1/results.json').read_text())
    for file,digest in multi['tools'].items():assert sha(ROOT/file)==digest
    for case in multi['cases'].values():
        assert sha(ROOT/case['master'])==case['master_sha256']
        for method in case['methods'].values():assert sha(ROOT/method['audition']['file'])==method['audition']['sha256']
    code=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    audit=dict(result='pass',version='0.4.0',ctest_count=5,paired_scenarios=8,
        vehicle_traces_bit_identical=True,other_templates_bit_identical=4,
        source_hashes_unchanged=True,frozen_baseline_files_verified=frozen,
        preceding_research_snapshot_files_verified=len(snapshot['files']),
        multi_resolution_recording_cases=len(multi['cases']),
        device=smoke,browser=browser,dna_pipeline=dna,
        scene='Ten independent float32 stems and 7.1.4 bed format verified; CTest compares stereo/12ch source samples and state.',
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(code)},
        limits=['No subjective realism or measured Lamborghini state/RPM/load calibration is inferred.',
                'Muted device test is not audible speaker or loopback validation.',
                'Physical structural/acoustic models, rev matching and future array audition remain open.'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    previous=json.loads((ROOT/'research/goal_progress_stereo_v1.json').read_text())
    progress=dict(goal_status='active',review_version='0.4.0',
        previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Multi-resolution shared stereo ablation with fixed controls and six recording checks; the real-recording improvement remains limited',
            'Dense phase-consistent V10 high-order source with explicit sample-rate protection and separate engineering spectrum data',
            'Mechanical/intake runtime separated; other four templates retain bit-identical render behaviour',
            'Eight matched-state comparison cases, 16 labelled PCM24 takes, source stems and 7.1.4 speaker bed',
            'Five CTests, current-version DNA interchange, muted device timing and browser playback verification',
            'Default build/launcher moved to separate build-v04; previous runtime artifacts preserved'],
        evidence=dict(implementation='research/V04高阶声源实现.md',review='research/V04试听.html',
            audit='renders/v0.4.0/workspace_audit.json',offline='references/analysis/multires_v1/results.json'),
        full_objective_audit=previous['full_objective_audit'],
        remaining_work=['Subjective feedback on V0.4 and RPM/load/state calibration; more upper-band energy is not proof of naturalness',
            'Separate imported synthesizer DNA pitch phase from the crank/firing clock consumed by the other layers; engine.c currently shares control.phase for both',
            'Improve audio/video event annotation with explicit uncertainty and disjoint generation checks',
            'Develop controlled downshift rev matching, coupling and fuel-cut/residual transitions',
            'Replace structural approximations and fit separate engine/air/road/room behaviour without misclassifying fit errors as physical noise',
            'Preserve independent spatial objects; measured acoustics and future hardware listening remain open',
            'Keep the broad objective active; this review candidate is concrete progress, not completion'])
    progress['full_objective_audit'][1]=dict(requirement='More realistic detailed engine sound across operating states',
        status='Incomplete: V0.4 adds dense high harmonics and bank phase consistency; actual spectral changes and unchanged state traces verified. Perceptual naturalness and Lamborghini calibration remain unproven.',
        evidence='renders/v0.4.0/verification.json; research/V04试听.html')
    (ROOT/'research/goal_progress_v04.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k in ['result','ctest_count','paired_scenarios','other_templates_bit_identical','frozen_baseline_files_verified']},indent=2))


if __name__=='__main__':main()
