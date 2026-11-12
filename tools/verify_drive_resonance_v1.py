"""Verify optional one-clock driving detail, unchanged zero path and owned recording."""
import argparse,csv,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(result='running',source_sha256={},commands=[],legacy=[],exports=[])
def run(argv,expected=0,timeout=600):
    started=time.perf_counter();proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=timeout)
    path=a.out/f'command_{len(r["commands"]):02}.log';path.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=proc.returncode,expected=expected,seconds=time.perf_counter()-started,log=path.name,sha256=sha(path)))
    print(json.dumps(dict(command=list(map(str,argv[:4])),exit=proc.returncode,log=str(path))),flush=True)
    assert proc.returncode==expected,(argv,proc.returncode,path);return proc.stdout
try:
    before=a.workspace/'references/analysis/drive_resonance_v1/before1';b=json.loads((before/'snapshot.json').read_text(encoding='utf-8'))
    assert b['result']=='before_snapshot_pass'
    for name,digest in b['files'].items():assert sha(before/name)==digest,name
    r['before_sha256']=sha(before/'snapshot.json');shutil.copy2(before/'prior_C_index.csv',a.out/'prior_C_index.csv')
    with (a.out/'prior_C_index.csv').open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
    r['modified_prior_C_H']=[row['文件'] for row in prior if sha(repo/row['文件'])!=row['SHA-256']]
    expected={'modules/atlas_drive/control.c','modules/atlas_drive/control.h','modules/atlas_drive/render.c','modules/atlas_drive/render.h',
        'modules/atlas_take/assets.c','modules/atlas_take/assets.h','modules/atlas_take/parameters.c','modules/atlas_take/player.c',
        'modules/atlas_take/player.h','modules/atlas_take/take.c','modules/atlas_take/take.h','modules/atlas_take_io/codec.c',
        'experiments/atlas_monitor_v1/audio.c','experiments/atlas_monitor_v1/audio.h','experiments/atlas_monitor_v1/ui.c','experiments/atlas_take_v1/checks.c',
        'experiments/catch_drive_v1/checks.c','experiments/drive_aux_v1/checks.c','experiments/startup_detail_host_v1/checks.c'}
    assert set(r['modified_prior_C_H'])==expected
    paths=[repo/row['文件'] for row in prior]
    paths += [v for folder in ('modules/drive_resonance','experiments/drive_resonance_v1') for v in (repo/folder).iterdir() if v.suffix in ('.c','.h')]
    assert len(paths)==519
    paths += [Path(__file__),repo/'tools/snapshot_drive_resonance_v1.py',repo/'Launch-Drive-Resonance-Study.cmd',repo/'handoff/CMakeLists.txt']
    paths += list((repo/'modules').rglob('CMakeLists.txt'))
    for path in paths:
        name=path.relative_to(repo).as_posix();target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);r['source_sha256'][name]=sha(path)
    r['input_sha256']={v.relative_to(repo).as_posix():sha(v) for v in (repo/'voices').rglob('*') if v.is_file() and v.suffix in ('.model','.rdetail','.residual','.start','.cb')}
    run(['cmake','-S',repo/'handoff','-B',a.build,'-G','Visual Studio 17 2022','-A','x64'])
    run(['cmake','--build',a.build,'--config','Release','--parallel','4'])
    result=run(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'])
    assert re.search(rb'100% tests passed(?:, 0 tests failed)? out of 51',result);r['Ctests_passed']=51
    shutil.copy2(a.build/'CMakeCache.txt',a.out/'CMakeCache.after_build.txt')
    (a.out/'bin').mkdir();r['binaries']={}
    for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslDriveResonance_device','VslAtlasMonitor'):
        path=a.build/'bin/Release'/f'{name}.exe';shutil.copy2(path,a.out/'bin'/path.name);r['binaries'][path.name]=sha(path)
    renders=a.out/'renders';renders.mkdir()
    for case in b['cases']:
        opts=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        run([a.out/'bin/VslAtlasDrive_probe.exe',*case['models'][:2],renders/case['name'],*opts])
        old=list((before/'renders').glob(case['name']+'_*.wav'));assert len(old)==28
        for path in old:assert path.read_bytes()==(renders/path.name).read_bytes(),path.name
        trace=case['name']+'_trace.csv';assert (before/'renders'/trace).read_bytes()==(renders/trace).read_bytes()
        r['legacy'].append(dict(name=case['name'],WAV_bytes_equal=len(old),trace_bytes_equal=True))
    device=a.out/'device';device.mkdir();run([a.out/'bin/VslDriveResonance_device.exe',device],timeout=120)
    r['device']=json.loads((device/'device.json').read_text());assert r['device']['result']=='pass'
    assert r['device']['record_hash']==r['device']['play_hash'] and r['device']['active_and_missing_support_observed']
    take=device/'detail_schema6.vslrun';header=take.read_bytes()[:80];assert int.from_bytes(header[8:12],'little')==6 and int.from_bytes(header[76:80],'little')==28
    for channels in (2,12):
        out=device/f'export_{channels}.wav';row=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',take,out,'--channels',channels]));assert row['verified'];r['exports'].append(row)
    actual,rate=sf.read(device/'recorded.wav',always_2d=True);stereo,rate2=sf.read(device/'export_2.wav',always_2d=True)
    assert rate==rate2==48000 and actual.shape==stereo.shape==(144123,2) and np.array_equal(actual,stereo)
    wide,rate3=sf.read(device/'export_12.wav',always_2d=True);assert rate3==48000 and wide.shape==(144123,12)
    assert r['exports'][0]['source_hash']==r['exports'][1]['source_hash']
    assert np.array_equal(wide[:,:2],stereo) and np.count_nonzero(wide[:,2:])==0
    r['source_and_front_2_12_exact']=True
    run([a.out/'bin/VslAtlasTake_render.exe',before/'old_schema5.vslrun',device/'must_reject_schema5.wav'],expected=3)
    run([before/'VslAtlasTake_render.exe',take,device/'must_reject_schema6.wav'],expected=3)
    assert not (device/'must_reject_schema5.wav').exists() and not (device/'must_reject_schema6.wav').exists()
    ui=a.out/'ui';ui.mkdir();run([a.out/'bin/VslAtlasMonitor.exe','--resonant-study','--ui-check',ui/'ui.json'],timeout=90)
    r['ui']=json.loads((ui/'ui.json').read_text());assert r['ui']['result']=='pass'
    from PIL import Image
    Image.open(ui/'ui.json.bmp').convert('RGB').save(ui/'window.png')
    r.update(result='driving_resonant_detail_technical_pass',prior_C_H=511,unchanged_prior_C_H=492,new_C_H=8,C_H_rows=519,
        schema=6,fields=28,original_idle_add_parameters_unchanged=True,
        moving35_recipe_or_native_default_changed=False,new_listening_acceptance=False,
        limits=['Local additive low candidate only; no moving35 replacement in driving atlas',
                'Support .9..1.1 with inner .96..1.04 is an engineering fade, not measured RPM/load coverage',
                'No new RPM/load evidence, hot-idle calibration or full acceleration timbre acceptance',
                'Short muted stereo device and own-control UI check, not long-run/manual mouse/physical7.1.4 acceptance'])
except Exception as e:r.update(result='failed',error=repr(e));raise
finally:
    r['evidence_sha256']={path.relative_to(a.out).as_posix():sha(path) for path in a.out.rglob('*') if path.is_file() and 'exact_sources' not in path.parts}
    (a.out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
