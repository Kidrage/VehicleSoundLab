"""Verify optional native detail controls, real muted device and owned schema5 takes."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
for name in ('bin','device'):(a.out/name).mkdir()
shutil.copy2(__file__,a.out/'executed_verify.py')
r=dict(result='running',commands=[],UI={},device={},human_accepted=False,visual_QA=False)
def run(cmd,cwd=repo):
    cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:4])),flush=True)
    done=subprocess.run(cmd,cwd=cwd,capture_output=True,timeout=180)
    path=a.out/f'command_{len(r["commands"]):02}.log';path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,cwd=str(cwd),exit_code=done.returncode,log=path.name,sha256=sha(path)))
    assert done.returncode==0,path.name
    return done.stdout

try:
    root=a.workspace/'references/analysis/startup_detail_host_v1'
    build=json.loads((root/'build1/report.json').read_text(encoding='utf-8'))
    assert build['result']=='build_and_46tests_pass'
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    binary=Path(build['build'])/'bin/Release'
    for name in ('VslAtlasMonitor.exe','VslAtlasMonitor_device_verify.exe','VslAtlasTake_device_checks.exe',
                 'VslAtlasTake_render.exe','VslStartupDetailHost_checks.exe'):
        shutil.copy2(binary/name,a.out/'bin'/name)
    r['binaries']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    # The old default context must still disable a control with no model.
    for mode in ('catch','startup-detail'):
        path=a.out/f'UI_{mode}.json'
        run([a.out/'bin/VslAtlasMonitor.exe',f'--{mode}-study','--muted','--ui-check',path])
        row=json.loads(path.read_text());assert row['passed'] and row['programmatic_own_window_controls']
        assert row['audio_started'] is False;r['UI'][mode]=row
    for name,malformed in (('missing_detail',False),('malformed_detail',True)):
        fixture=a.out/name;(fixture/'voices/startup_settle_v1').mkdir(parents=True)
        shutil.copy2(repo/'voices/startup_settle_v1/A start cabin settle.model',fixture/'voices/startup_settle_v1/A start cabin settle.model')
        if malformed:
            (fixture/'voices/startup_detail_v1').mkdir()
            (fixture/'voices/startup_detail_v1/A startup settling detail.residual').write_text('VSL_SOUND_RESIDUAL 1 48000 12 32\n',encoding='ascii')
        run([a.out/'bin/VslStartupDetailHost_checks.exe','--missing-detail'],cwd=fixture)
    r['missing_and_malformed_detail_transaction_checked']=True
    run([a.out/'bin/VslAtlasMonitor_device_verify.exe',a.out/'device','--stereo-bed','--startup-detail'])
    for name in ('bench','pedals','stopped','cabin_restart'):
        row=json.loads((a.out/'device'/f'{name}.json').read_text())
        assert row['healthy'] and row['offline_float_equal'] and row['queue_empty']==0
        assert any(v['catch_gain']>0 and v['startup_gain']>0 for v in row['controls'])
        if name!='stopped':assert any(v['residual_gain']>0 for v in row['controls'])
        r['device'][name]={k:row[k] for k in ('frames','healthy','offline_float_equal','queue_empty','budget_exceeded','render_mean_ms','render_max_ms')}
    take=a.out/'startup_detail_take.vslrun'
    run([a.out/'bin/VslAtlasTake_device_checks.exe',take,'--stereo-bed','--startup-detail'])
    row=json.loads(take.with_name(take.name+'.json').read_text())
    assert row['verified'] and row['startup_detail'] and row['record_hash']==row['play_hash'];r['take']=row
    header=take.read_bytes()[:80]
    assert int.from_bytes(header[8:12],'little')==5 and int.from_bytes(header[76:80],'little')==27
    r['exports']=[]
    for channels in (2,12):
        export=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',take,a.out/f'take_{channels}.wav','--channels',channels]))
        assert export['verified'];r['exports'].append(export)
    assert r['exports'][0]['source_hash']==r['exports'][1]['source_hash']
    prior=a.workspace/'references/analysis/catch_drive_v1/verification1'
    old=json.loads((prior/'report.json').read_text())
    legacy=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',prior/'catch_take.vslrun',a.out/'old_catch_take.wav']))
    assert legacy['verified'] and legacy['audio_hash']==old['exports'][0]['audio_hash']
    assert legacy['source_hash']==old['exports'][0]['source_hash'];r['old_schema5_take']=legacy
    assert row['render_id']==old['take']['render_id']
    y,rate=sf.read(a.out/'take_2.wav',always_2d=True)
    assert rate==48000 and np.isfinite(y).all() and len(y)==144123
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    r.update(result='native_startup_detail_function_pass',take_schema=5,control_fields=27,
        renderer_identity_unchanged=True,old_schema5_output_and_source_hash_equal=True,
        limits=['Short muted stereo device only; no long-run or physical12speaker acceptance',
                'Own-window controls checked programmatically; no screenshot, dialog or listening acceptance',
                'Single A settling detail anchor; high-RPM device actions test functions, not calibrated timbre'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],UI=r['UI'],device=r['device'],take=r.get('take'))))
