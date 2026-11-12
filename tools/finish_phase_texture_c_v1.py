"""Bind the optional C implementation, device evidence and append-only acceptance."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from PIL import Image
from drive_evidence_v1.sources import sha
root=a.workspace/'references/analysis/phase_texture_c_v1'
a.out.mkdir(parents=True,exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
r=dict(schema='vsl.phase-texture-C-summary/1',result='running')
try:
    before=read(root/'before/report.json');verification=read(root/'verification1/report.json')
    device=read(root/'device1/device.json');ui=read(root/'ui1/ui.json');review=read(root/'review1/report.json')
    assert before['result']=='prior_472_C_H_and_players_preserved'
    assert verification['result']=='pass' and device['result']==ui['result']=='pass'
    assert review['result']=='five_native_review_clips_HTTP_decode_pass'
    assert '100% tests passed out of 47' in (root/'ctest2.log').read_text(encoding='utf-8-sig')
    assert not any(word in (root/'build2.log').read_text(encoding='utf-8-sig') for word in ('warning C','error C'))
    budget=512/48
    for name in ('baseline','live','stopped','restarted'):
        row=device[name];assert row['offline_float_equal'] and row['queue_empty']==row['trace_overflow']==0
        assert row['render_ms_max']<budget
        trace=read(root/f'device1/{name}_controls.json')
        assert trace['events'][0]['phase_texture']==1
    assert {v['phase_texture'] for v in read(root/'device1/live_controls.json')['events']}=={0,1}
    baseline,rate=sf.read(root/'device1/baseline.wav',dtype='float32',always_2d=True)
    restart,rate2=sf.read(root/'device1/restarted.wav',dtype='float32',always_2d=True)
    assert rate==rate2==48000 and np.array_equal(restart,baseline[:len(restart)])
    probe,rate=sf.read(root/'verification1/seed_8121907_amount_1/mix.wav',dtype='float32',always_2d=True)
    # Native host has its documented linear240-sample onset; after that its
    # dry source is exactly the standalone native OSC source, not the PCG clip.
    assert np.array_equal(baseline[240:],probe[240:len(baseline)])
    assert ui['program_internal_control_test'] and not ui['manual_interaction_verified']
    image=Image.open(root/'ui1/ui.bmp');image.save(root/'ui1/ui.png')
    assert image.size==(560,710)
    with (root/'before/C文件索引.csv').open(encoding='utf-8-sig') as stream:old={v['文件']:v for v in csv.DictReader(stream)}
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:now={v['文件']:v for v in csv.DictReader(stream)}
    assert len(old)==472 and len(now)==478 and set(old)<=set(now)
    changed=[]
    for name,row in now.items():
        assert sha(repo/name)==row['SHA-256'],name
        if name in old:
            assert {k:v for k,v in row.items() if k!='SHA-256'}=={k:v for k,v in old[name].items() if k!='SHA-256'},name
            if row['SHA-256']!=old[name]['SHA-256']:changed.append(name)
    assert len(changed)==6
    assert not any(name.startswith(('src/','modules/sound_dna/')) for name in changed)
    # Verification1 was captured before the later host flag/UI self-test edits.
    # Every measured portable source and probe must still be byte-identical.
    for name,digest in verification['source_sha256'].items():
        if name.endswith(('.c','.h')) and name.startswith(('modules/','src/','experiments/phase_texture_c_v1/')):
            assert sha(repo/name)==digest,name
    build=repo/'build-phase-texture-c-v1'
    source_paths=[repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt']
    for folder in ('src','modules','experiments','tests'):
        source_paths.extend(x for x in (repo/folder).rglob('*') if x.suffix in ('.c','.h') or x.name=='CMakeLists.txt')
    for path in source_paths:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    binaries={}
    for folder in ('bin/Release','Release'):
        for path in (build/folder).glob('*.exe'):
            target=a.out/'bin'/folder/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            binaries[str(path.relative_to(build))]=sha(path)
    r.update(result='C_and_short_native_function_pass',date='2026-11-12',CTest_passed=47,
        offline_acceptance=read(repo/'research/phase_texture_v1_acceptance.json'),
        native_listening_accepted=False,C_H_count=len(now),old_C_H_unchanged=len(old)-len(changed),changed_old_C_H=changed,
        original_sound_dna_and_models_unchanged=True,verification=verification,device=device,UI=ui,review=review,
        binary_sha256=binaries,source_sha256={str(x.relative_to(repo)).replace('\\','/'):sha(x) for x in source_paths},
        current_take_schema=5,take_control_fields=27,new_phase_in_take_or_driver=False,
        previous_players_preserved=True,short_device_budget_ms=budget,
        limitations=['Native listening not inferred from offline direction acceptance',
                     'No full states/RPM/load calibration or physical12speaker/longrun acceptance',
                     'Motion RNG differs from accepted offline PCG sequence; filter/interpolation/scale are checked'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(repo/'research/phase_texture_c_v1_summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],C_H=len(now),old_unchanged=r['old_C_H_unchanged'],max_device_ms=max(device[k]['render_ms_max'] for k in ('baseline','live','stopped','restarted')))))
