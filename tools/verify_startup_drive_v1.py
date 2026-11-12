"""Check legacy audio, startup isolation, owned schema4 replay and actual stereo device."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
root=a.workspace/'references/analysis/startup_drive_v1';build=repo/'build-startup-drive-v1'
a.out.mkdir(parents=True,exist_ok=False)
for name in ['bin','renders','device']:(a.out/name).mkdir()
r=dict(result='running',commands=[],legacy=[],device={},exports=[],human_accepted=False,UI_interaction_checked=False)
shutil.copy2(__file__,a.out/'executed_verify.py');r['source_sha256']=sha(__file__)
def run(cmd,expected=0):
    cmd=list(map(str,cmd));print(json.dumps({'running':cmd[:4]}),flush=True)
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=180)
    name=f'command_{len(r["commands"]):02}.log';(a.out/name).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=name,sha256=sha(a.out/name)))
    assert done.returncode==expected,name
    return done.stdout
try:
    proof=json.loads((root/'build2/report.json').read_text(encoding='utf-8'));assert proof['result']=='build_and_43tests_pass'
    for name,digest in proof['source_sha256'].items():assert sha(repo/name)==digest,name
    for path in (build/'bin/Release').glob('VslAtlas*.exe'):shutil.copy2(path,a.out/'bin'/path.name)
    r['binary_sha256']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    old_root=a.workspace/'references/analysis/stereo_bed_v1'
    before=json.loads((old_root/'before/report.json').read_text(encoding='utf-8'))
    probe=a.out/'bin/VslAtlasDrive_probe.exe'
    for case in before['cases']:
        bed=case['name'].startswith('E_');key=case['name']+('_bed' if bed else '')
        old=(old_root/'verification1/renders' if bed else old_root/'before/renders')
        prefix=a.out/'renders'/key;opts=case['options']+(['--stereo-bed','1'] if bed else [])
        run([probe,*case['models'][:2],prefix,*opts])
        files=list(old.glob(key+'_*.wav'));assert len(files)==26
        for path in files:assert path.read_bytes()==(prefix.parent/path.name).read_bytes(),path.name
        assert (old/(key+'_trace.csv')).read_bytes()==prefix.with_name(key+'_trace.csv').read_bytes()
        r['legacy'].append(dict(name=key,WAV_bytes_equal=26,controls_bytes_equal=True))
    case=before['cases'][2];prefix=a.out/'renders/E_startup'
    profile=repo/'voices/startup_drive_v1/A cabin motion.start'
    run([probe,*case['models'][:2],prefix,*case['options'],'--stereo-bed','1','--startup-profile',profile,'--startup-gain','.5'])
    source_names=['dna_raw','dna','residual_raw','residual','harmonic_body_raw','harmonic_body','auxiliary',
                  'aux_raw_intake','aux_raw_mechanical','aux_raw_air_left','aux_raw_air_right','aux_raw_road','aux_raw_wind']
    old=old_root/'verification1/renders'
    for name in source_names:assert (old/('E_objects2_bed_'+name+'.wav')).read_bytes()==prefix.with_name(prefix.name+'_'+name+'.wav').read_bytes(),name
    assert (old/'E_objects2_bed_trace.csv').read_bytes()==prefix.with_name(prefix.name+'_trace.csv').read_bytes()
    signal,rate=sf.read(prefix.with_name(prefix.name+'_startup.wav'),always_2d=True)
    assert rate==48000 and np.max(abs(signal[:24000]))>0 and np.max(abs(signal[48000:]))<1e-7
    r['startup']=dict(independent13_source_stems_equal=True,controller_trace_equal=True,
                      peak=float(np.max(abs(signal))),no_PCM_or_pitch_sweep=True)
    old_take=a.workspace/'references/analysis/stereo_bed_v1/verification1/bed_take.vslrun'
    run([root/'before/bin/VslAtlasTake_render.exe',old_take,a.out/'old_schema3.wav'])
    run([a.out/'bin/VslAtlasTake_render.exe',old_take,a.out/'must_reject_schema3.wav'],expected=3)
    assert not (a.out/'must_reject_schema3.wav').exists()
    run([a.out/'bin/VslAtlasMonitor_device_verify.exe',a.out/'device','--stereo-bed','--startup'])
    for name in ['bench','pedals','stopped','cabin_restart']:
        row=json.loads((a.out/'device'/(name+'.json')).read_text(encoding='utf-8'))
        assert row['healthy'] and row['offline_float_equal'] and row['queue_empty']==0
        r['device'][name]={k:row[k] for k in ['frames','healthy','offline_float_equal','queue_empty','budget_exceeded','render_max_ms']}
    run([a.out/'bin/VslAtlasTake_device_checks.exe',a.out/'startup_take.vslrun','--stereo-bed','--startup'])
    take=json.loads((a.out/'startup_take.vslrun.json').read_text(encoding='utf-8'))
    assert take['verified'] and take['record_hash']==take['play_hash'];r['take']=take
    header=(a.out/'startup_take.vslrun').read_bytes()[:108]
    assert int.from_bytes(header[8:12],'little')==4 and int.from_bytes(header[76:80],'little')==26
    for channels in [2,12]:
        row=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',a.out/'startup_take.vslrun',a.out/f'take_{channels}.wav','--channels',channels]))
        assert row['verified'];r['exports'].append(row)
    assert r['exports'][0]['source_hash']==r['exports'][1]['source_hash']
    r.update(result='integrated_startup_function_pass',take_schema=4,control_fields=26,
        old_schema3_player_preserved=True,limits=['Short muted stereo device only; not long-run or physical12speaker',
            'A startup and E running-cabin references differ; this is an explicit engineering preview',
            'Two PSD endpoints do not identify a motor clock, physical crank duration or catching combustion'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],device=r['device'],take_schema=r.get('take_schema'))))
