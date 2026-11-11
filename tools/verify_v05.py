"""Verify concrete V0.5 evidence and preserve all preceding media/baselines."""
from pathlib import Path
import csv
import hashlib
from html.parser import HTMLParser
import json
import struct
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'renders/v0.5.0'
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    report=json.loads((OUT/'verification.json').read_text());assert report['version']=='0.5.0'
    for name,digest in report['files'].items():assert sha(OUT/name)==digest,name
    for name,case in report['cases'].items():
        for version in ['v04','v05']:
            item=case[version]['audition'];file=OUT/item['file']
            assert sha(file)==item['sha256']
            x,sr=sf.read(file,always_2d=True);info=sf.info(file)
            assert sr==48000 and info.channels==2 and info.subtype=='PCM_24'
            assert np.isfinite(x).all() and abs(x).max()<=.850001
            assert abs(10*np.log10(np.mean(x*x))-(case[version]['rms_dbfs']+item['gain_db']))<.001
    for profile in range(5):
        a=OUT/f'compat_profile{profile}_v04.wav';b=OUT/f'compat_profile{profile}_v05.wav'
        assert a.read_bytes()==b.read_bytes() and sha(a)==report['factory_steady_compatibility'][str(profile)]['sha256']
    tests=ET.parse(OUT/'ctest.xml').getroot();assert tests.attrib['tests']=='7' and tests.attrib['failures']=='0'
    assert {x.attrib['name'] for x in tests.findall('testcase')}=={
        'dsp_invariants','driving_states','state_layer_response','high_order_sources',
        'independent_clocks','transmission_rev_match','spatial_objects'}
    dna=json.loads((OUT/'dna_check/dna_pipeline_check.json').read_text())
    assert dna['result']=='pass' and dna['dsp_version']=='0.5.0'
    assert dna['renderer_sha256']==sha(ROOT/'build-v05/Release/vsl_render.exe')
    smoke=json.loads((OUT/'ui_smoke.json').read_text())
    assert smoke==report['device'] and smoke['dsp']=='0.5.0' and smoke['device_stream_muted']
    assert smoke['queue_empty_observations']==0 and .95<smoke['device_seconds']/smoke['wall_seconds']<1.02
    assert smoke['render_ms_mean']<512/48
    browser=json.loads((OUT/'browser_qa.json').read_text())
    assert browser['result']=='pass' and browser['metadata_loads']==13
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ['src','href'] and not v.startswith(('http:','https:','#')):assert (ROOT/'research'/v).resolve().is_file(),v
    Links().feed((ROOT/'research/V05试听.html').read_text(encoding='utf-8'))
    with (OUT/'downshift_v05.csv').open() as f:rows=list(csv.DictReader(f))
    braking=[x for x in rows if float(x['seconds'])>=10.5]
    assert all(float(b['speed_kph'])<=float(a['speed_kph'])+.001 for a,b in zip(braking,braking[1:]))
    assert len({x['hits'] for x in braking})==1,'No new timed hits may be invented by internal blips'
    blips=[x for x in braking if float(x['blip'])>0]
    assert len(blips)>0 and all(float(x['throttle'])<.001 and float(x['clutch_transfer'])==0 for x in blips)
    assert report['downshift']['trace']['matched_engagements']==6
    # The independent stems carry actual sound during the match, not only UI labels.
    stem_measurements={}
    spans={'before':[11.32,11.49],'blip':[11.55,11.67],'after':[11.84,12.0]}
    for file in sorted((OUT/'stems').glob('downshift_*.wav')):
        x,sr=sf.read(file);info=sf.info(file)
        assert info.subtype=='FLOAT' and info.channels==1 and info.frames==18*48000
        measurements={}
        for key,(lo,hi) in spans.items():
            y=x[int(lo*sr):int(hi*sr)];measurements[key]=float(10*np.log10(max(float(np.mean(y*y)),1e-30)))
        stem_measurements[file.stem]=measurements
    assert len(stem_measurements)==10
    assert stem_measurements['downshift_intake']['blip']>stem_measurements['downshift_intake']['before']+6
    assert stem_measurements['downshift_exhaust_left']['blip']>stem_measurements['downshift_exhaust_left']['before']+1
    scene=json.loads((OUT/'drive_714_scene.json').read_text())
    assert scene['dsp_version']=='0.5.0' and len(scene['objects'])==10
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        file=OUT/obj['file'];info=sf.info(file)
        assert info.channels==1 and info.subtype=='FLOAT' and info.frames==30*48000
        assert sha(file)==obj['sha256']
    with (OUT/'drive_714_v05.wav').open('rb') as f:
        assert f.read(4)==b'RIFF';f.read(4);assert f.read(4)==b'WAVE';chunks={}
        while True:
            name,size=struct.unpack('<4sI',f.read(8))
            if name==b'data':break
            chunks[name]=f.read(size)
            if size%2:f.read(1)
    assert struct.unpack('<HHI',chunks[b'fmt '][:8])==(65534,12,48000)
    assert struct.unpack('<I',chunks[b'fmt '][20:24])[0]==0x2d63f
    assert struct.unpack('<I',chunks[b'fact'][:4])[0]==30*48000
    frozen={}
    for version in ['v0.1.0','v0.2.0','v0.3.0','v0.4.0']:
        folder=ROOT/'baselines'/version;manifest=json.loads((folder/'manifest.json').read_text())
        for entry in manifest['files']:assert sha(folder/entry['path'])==entry['sha256'],(version,entry['path'])
        frozen[version]=len(manifest['files'])
    masters=json.loads((ROOT/'references/analysis/joint_stereo_v1/results.json').read_text())
    for item in masters['sources'].values():assert sha(ROOT/item['master'])==item['sha256']
    for identity in ['A','B']:
        raw=json.loads((ROOT/f'references/raw/{identity}_provenance.json').read_text())
        assert sha(ROOT/'references/raw'/raw['original_file'])==raw['sha256']
    snapshot=json.loads((ROOT/'references/analysis/joint_stereo_v1/review_manifest.json').read_text())
    for entry in snapshot['files']:assert sha(ROOT/entry['path'])==entry['sha256'],entry['path']
    code=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    audit=dict(result='pass',version='0.5.0',ctest_count=7,paired_scenarios=6,audition_takes=13,
        factory_steady_bit_identical=5,braking_blips_no_new_hits=True,downshift=report['downshift']['trace'],
        stem_windows_file_seconds=spans,stem_rms_dbfs=stem_measurements,
        source_hashes_unchanged=True,frozen_baseline_files_verified=frozen,
        preceding_research_snapshot_files_verified=len(snapshot['files']),
        device=smoke,browser=browser,dna_pipeline=dna,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(code)},
        limits=['Control correctness and actual source energy changes are established; subjective realism is unproven.',
                'New vehicle trajectories intentionally differ from V0.4. Timing remains engineering, not video fitted.',
                'Source stems and speaker bed verified; physical acoustics and array audition remain open.'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    previous=json.loads((ROOT/'research/goal_progress_v04.json').read_text())
    full=previous['full_objective_audit']
    full[1]=dict(requirement=full[1]['requirement'],status='Incomplete: V0.5 adds distinct rev-match layer response and independent imported-DNA clocks. Naturalness and Lamborghini state/load calibration remain unproven.',evidence='renders/v0.5.0/workspace_audit.json; research/V05试听.html')
    full[4]=dict(requirement=full[4]['requirement'],status='Partial: controlled clutch disconnect/match/engage and bounded internal downshift blips implemented; physical powertrain, fuel-cut, NVH and acoustic models remain engineering approximations.',evidence='src/drive/shift.c; src/profiles/transmission.c; tests/test_shift.c')
    progress=dict(goal_status='active',review_version='0.5.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Independent engine-cycle and imported-DNA clocks, with active non-DNA stem/pitch tests',
            'Modular bounded shift matching, clutch transfer, effective throttle, sport hold, safe braking downshift and distinct layer response',
            'Six comparison pairs and closed-pedal downshift audition, actual trace/stem measurements and float32 7.1.4 speaker bed',
            'Seven CTests, current DNA interchange, muted device timing, native preview and browser checks',
            'Separate build-v05 and new default launcher; all four frozen versions and approved media verified intact'],
        evidence=dict(implementation='research/V05降挡与独立时钟.md',review='research/V05试听.html',audit='renders/v0.5.0/workspace_audit.json'),
        full_objective_audit=full,
        remaining_work=['Listen to V0.5 and calibrate RPM/load/state spectra with explicit reference uncertainty',
            'Strengthen video/audio event labels and disjoint generation checks; no new precise telemetry is established this iteration',
            'Develop fuel-cut/residual excitation, physical torque/inertia and structural/acoustic models',
            'Measure separate engine/air/road/room transfer, preserve stereo coherence and validate future 7.1.4 hardware',
            'Keep broad objective active; this frozen review is progress, not completion'])
    (ROOT/'research/goal_progress_v05.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ['result','ctest_count','factory_steady_bit_identical','downshift','frozen_baseline_files_verified']},indent=2))

if __name__=='__main__':main()
