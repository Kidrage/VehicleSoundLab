"""Verify opt-in catch integration against frozen audio and actual device/take."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
for name in ('bin','renders','device'):(a.out/name).mkdir()
shutil.copy2(__file__,a.out/'executed_verify.py')
r=dict(result='running',commands=[],legacy=[],scene=[],device={},human_accepted=False,UI_interaction_checked=False)
def run(cmd,expected=0):
    cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:4])),flush=True)
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=180)
    name=f'command_{len(r["commands"]):02}.log';(a.out/name).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=name,sha256=sha(a.out/name)))
    assert done.returncode==expected,name
    return done.stdout
def audio(path):
    y,rate=sf.read(path,always_2d=True);assert rate==48000 and np.isfinite(y).all();return y
try:
    root=a.workspace/'references/analysis/catch_drive_v1'
    proof=json.loads((root/'build2/report.json').read_text());assert proof['result']=='build_and_45tests_pass'
    for name,digest in proof['source_sha256'].items():assert sha(repo/name)==digest,name
    for file in (repo/'build-catch-drive-v1/bin/Release').glob('VslAtlas*.exe'):shutil.copy2(file,a.out/'bin'/file.name)
    shutil.copy2(repo/'build-catch-drive-v1/bin/Release/VslCatchDrive_probe.exe',a.out/'bin/VslCatchDrive_probe.exe')
    r['binaries']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    cases=json.loads((a.workspace/'references/analysis/stereo_bed_v1/before/report.json').read_text())['cases']
    old=a.workspace/'references/analysis/startup_drive_v1/verification1/renders';probe=a.out/'bin/VslAtlasDrive_probe.exe'
    for case in cases:
        bed=case['name'].startswith('E_');key=case['name']+('_bed' if bed else '');prefix=a.out/'renders'/key
        opts=case['options']+(['--stereo-bed','1'] if bed else [])
        run([probe,*case['models'][:2],prefix,*opts])
        frozen=list(old.glob(key+'_*.wav'));assert len(frozen)==27
        for file in frozen:assert file.read_bytes()==(prefix.parent/file.name).read_bytes(),file.name
        assert (old/(key+'_trace.csv')).read_bytes()==prefix.with_name(key+'_trace.csv').read_bytes()
        r['legacy'].append(dict(name=key,WAV_bytes_equal=len(frozen),controls_bytes_equal=True))
    case=cases[2];prefix=a.out/'renders/E_startup'
    starter=repo/'voices/startup_drive_v1/A cabin motion.start';model=repo/'voices/startup_settle_v1/A start cabin settle.model'
    profile=repo/'voices/catch_bloom_v1/A cabin catch.cb'
    run([probe,*case['models'][:2],prefix,*case['options'],'--stereo-bed','1','--startup-profile',starter,'--startup-gain','.5'])
    frozen=list(old.glob('E_startup_*.wav'));assert len(frozen)==27
    for file in frozen:assert file.read_bytes()==(prefix.parent/file.name).read_bytes(),file.name
    assert (old/'E_startup_trace.csv').read_bytes()==prefix.with_name(prefix.name+'_trace.csv').read_bytes()
    r['legacy'].append(dict(name='E_startup',WAV_bytes_equal=27,controls_bytes_equal=True))
    missing=a.out/'renders/missing_profile'
    run([probe,*case['models'][:2],missing,'--catch-gain','.5'],expected=2)
    assert not list(missing.parent.glob(missing.name+'*'))
    reference=a.workspace/'references/analysis/catch_bloom_v1/render1/renders'
    current={}
    for channels in (2,12):
        for amount in (0,.5,1):
            key=f'{channels}_{amount:.1f}';prefix=a.out/'renders'/('catch_'+key)
            run([a.out/'bin/VslCatchDrive_probe.exe',model,starter,profile,prefix,amount,channels])
            values={name:audio(prefix.with_name(prefix.name+'_'+name+'.wav')) for name in ('mix','raw','dna','startup','catch_bloom')}
            for name in ('raw','dna','startup'):
                assert prefix.with_name(prefix.name+'_'+name+'.wav').read_bytes()==(reference/(key+'_'+name+'.wav')).read_bytes(),(key,name)
            assert prefix.with_name(prefix.name+'_trace.csv').read_bytes()==(reference/(key+'_trace.csv')).read_bytes()
            old_mix=audio(reference/(key+'_mix.wav'));old_delta=audio(reference/(key+'_bloom.wav'))
            mix_error=float(np.max(abs(values['mix']-old_mix)));delta_error=float(np.max(abs(values['catch_bloom']-old_delta)))
            assert mix_error<3e-8 and delta_error<6e-8
            if amount==0:assert np.array_equal(values['mix'],old_mix) and np.max(abs(values['catch_bloom']))==0
            if channels==12:
                assert np.array_equal(values['mix'][:,:2],current[f'2_{amount:.1f}']['mix']) and np.max(abs(values['mix'][:,2:]))==0
                assert np.array_equal(values['catch_bloom'],current[f'2_{amount:.1f}']['catch_bloom'])
            current[key]=values;r['scene'].append(dict(channels=channels,amount=amount,mix_error=mix_error,delta_error=delta_error,
                driver_trace_byte_equal=True,peak=float(np.max(abs(values['mix'])))))
    old_take=a.workspace/'references/analysis/startup_drive_v1/verification1/startup_take.vslrun'
    run([root/'before/bin/VslAtlasTake_render.exe',old_take,a.out/'old_schema4.wav'])
    run([a.out/'bin/VslAtlasTake_render.exe',old_take,a.out/'must_reject_schema4.wav'],expected=3)
    assert not (a.out/'must_reject_schema4.wav').exists()
    run([a.out/'bin/VslAtlasMonitor_device_verify.exe',a.out/'device','--stereo-bed','--catch'])
    for name in ('bench','pedals','stopped','cabin_restart'):
        row=json.loads((a.out/'device'/(name+'.json')).read_text())
        assert row['healthy'] and row['offline_float_equal'] and row['queue_empty']==0
        assert any(v['catch_gain']>0 for v in row['controls'])
        r['device'][name]={k:row[k] for k in ('frames','healthy','offline_float_equal','queue_empty','budget_exceeded','render_max_ms')}
    run([a.out/'bin/VslAtlasTake_device_checks.exe',a.out/'catch_take.vslrun','--stereo-bed','--catch'])
    take=json.loads((a.out/'catch_take.vslrun.json').read_text());assert take['verified'] and take['record_hash']==take['play_hash'];r['take']=take
    header=(a.out/'catch_take.vslrun').read_bytes()[:108]
    assert int.from_bytes(header[8:12],'little')==5 and int.from_bytes(header[76:80],'little')==27
    r['exports']=[]
    for channels in (2,12):
        row=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',a.out/'catch_take.vslrun',a.out/f'take_{channels}.wav','--channels',channels]))
        assert row['verified'];r['exports'].append(row)
    assert r['exports'][0]['source_hash']==r['exports'][1]['source_hash']
    for name,digest in proof['source_sha256'].items():assert sha(repo/name)==digest,name
    r.update(result='integrated_catch_function_pass',old_schema4_player_preserved=True,take_schema=5,control_fields=27,
        limits=['Short muted stereo device, not long-run/physical12speaker/UI interaction or listening acceptance',
            'A startup cabin study uses engineering catch pitch/timing; full source state restoration incomplete'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],device=r['device'],take_schema=r.get('take_schema'))))
