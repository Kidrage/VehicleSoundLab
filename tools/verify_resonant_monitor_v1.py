"""Verify the native full-mixture monitor without changing fitted parameters."""
import argparse,csv,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.resonant-monitor-verification/1',result='running',source_sha256={},input_sha256={},commands=[])
def bind(path):
    path=Path(path);r['input_sha256'][str(path)]=sha(path);return path
def run(argv,timeout=600):
    started=time.perf_counter();proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=timeout)
    log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=proc.returncode,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log)))
    print(json.dumps(dict(command=r['commands'][-1]['argv'],exit=proc.returncode,log=str(log))),flush=True)
    assert proc.returncode==0,(argv,proc.returncode,log)
    return proc
def frozen(relative):
    root=a.workspace/'baselines/resonant_source_v1'
    manifest=json.loads(bind(root/'manifest.json').read_text(encoding='utf-8'))
    row=next(v for v in manifest['files'] if v['path']==relative)
    path=bind(root/relative);assert sha(path)==row['sha256'];return path
try:
    index=bind(repo/'handoff/C文件索引.csv');shutil.copy2(index,a.out/'prior_C_index.csv')
    with index.open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
    assert len(prior)==500
    for row in prior:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    paths=[repo/row['文件'] for row in prior]
    paths += [v for folder in ('modules/resonant_monitor','experiments/resonant_monitor_v1') for v in (repo/folder).iterdir() if v.suffix in ('.c','.h')]
    assert len(paths)==511
    paths += [Path(__file__),repo/'Launch-Resonant-Source.cmd',repo/'handoff/CMakeLists.txt']
    paths += [v for v in (repo/'modules').rglob('CMakeLists.txt')]
    for path in paths:
        name=path.relative_to(repo).as_posix();target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][name]=sha(path)
    for path in (repo/'voices').rglob('*'):
        if path.suffix in ('.model','.rdetail'):bind(path)
    run(['cmake','-S',repo/'handoff','-B',a.build,'-G','Visual Studio 17 2022','-A','x64'])
    run(['cmake','--build',a.build,'--config','Release','--parallel','4'])
    result=run(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'])
    assert re.search(rb'100% tests passed(?:, 0 tests failed)? out of 50',result.stdout)
    r['Ctests_passed']=50
    cache=bind(a.build/'CMakeCache.txt');shutil.copy2(cache,a.out/'CMakeCache.after_build.txt')
    r['binaries']={}
    for name in ('VslResonantMonitor','VslResonantMonitor_verify'):
        path=a.build/'bin/Release'/f'{name}.exe';shutil.copy2(path,a.out/path.name);r['binaries'][path.name]=sha(path)
    device=a.out/'device';device.mkdir()
    run([a.out/'VslResonantMonitor_verify.exe',device],timeout=180)
    r['device']=[]
    for name in ('moving','low','stopped','restart'):
        path=device/f'{name}.json';row=json.loads(path.read_text())
        assert row['healthy'] and row['muted'] and row['offline_float_equal']
        assert row['frames']==(144123 if name in ('moving','low') else 24637 if name=='restart' else row['frames'])
        if name=='stopped':assert row['release']==480
        r['device'].append(dict(name=name,**row,file=path.relative_to(a.out).as_posix(),sha256=sha(path)))
    r['dry_comparisons']=[]
    for name in ('moving_35','idle_add','idle_35'):
        path=device/f'{name}_dry.wav';ref=frozen(f'evidence/verify2/{name}_C.wav')
        actual,rate=sf.read(path,always_2d=True);expected,ref_rate=sf.read(ref,always_2d=True)
        assert rate==ref_rate==48000 and actual.shape==expected.shape==(384000,2)
        error=float(abs(actual-expected).max());assert error==0,(name,error)
        r['dry_comparisons'].append(dict(name=name,frames=len(actual),max_FS=error,float_exact=True,
            file=path.relative_to(a.out).as_posix(),sha256=sha(path)))
    ui=a.out/'ui';ui.mkdir();run([a.out/'VslResonantMonitor.exe','--ui-checks',ui],timeout=90)
    r['ui']=json.loads((ui/'ui.json').read_text());assert r['ui']['result']=='pass'
    from PIL import Image
    for name in ('moving','low'):Image.open(ui/f'{name}.bmp').convert('RGB').save(ui/f'{name}.png')
    r.update(result='native_monitor_technical_pass',prior_C_H_unchanged=500,new_C_H=11,C_H_rows=511,
        new_parameters_or_room_or_PCM=False,driver_or_take_integration=False,new_listening_acceptance=False,
        limits=['Own-program UI messages and screenshots; no manual mouse verification',
                'Short muted stereo device test; no long-run or physical 7.1.4 acceptance',
                'Fixed-context source and limited pitch .9..1.1, not a calibrated RPM/load atlas',
                'Idle listening remains pending; moving 35% retained without new tuning'])
except Exception as error:
    r.update(result='failed',error=repr(error));raise
finally:
    (a.out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],Ctests=r['Ctests_passed'],dry_exact=len(r['dry_comparisons']),device=len(r['device']))),flush=True)
