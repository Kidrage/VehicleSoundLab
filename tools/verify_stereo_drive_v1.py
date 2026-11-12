"""Verify the single-driver stereo adapter, device lifecycle and owned schema7."""
import argparse, csv, hashlib, json, re, shutil, subprocess, sys, time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','build','out'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--reuse',type=Path,help='Reuse bound completed checks after evidence-script-only correction')
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from PIL import Image
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(result='running',commands=[],sources={},devices={},legacy=[])
def run(argv,expected=0,timeout=180):
    started=time.perf_counter();proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=timeout)
    log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit=proc.returncode,expected=expected,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log)))
    print(json.dumps(dict(command=str(argv[0]),exit=proc.returncode,log=str(log))),flush=True)
    assert proc.returncode==expected,(argv,log);return proc.stdout
try:
    before=a.workspace/'references/analysis/stereo_drive_v1/before1'
    old=json.loads((before/'snapshot.json').read_text(encoding='utf-8'))
    assert old['result']=='before_snapshot_pass'
    for name,digest in old['files'].items():assert sha(before/name)==digest,name
    shutil.copy2(before/'prior_C_index.csv',a.out/'prior_C_index.csv')
    with (a.out/'prior_C_index.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    r['modified_prior_C_H']=[v['文件'] for v in rows if sha(repo/v['文件'])!=v['SHA-256']]
    assert set(r['modified_prior_C_H'])=={
        'modules/drive_resonance/bank.c','modules/drive_resonance/bank.h',
        'modules/drive_resonance/voice.c','modules/drive_resonance/voice.h',
        'modules/atlas_take_io/codec.c','experiments/atlas_monitor_v1/ui.c',
        'experiments/drive_resonance_v1/checks.c','experiments/drive_resonance_v1/device.c','experiments/atlas_take_v1/checks.c',
        'experiments/drive_resonance_v1/ui_checks.c'}
    paths=[repo/v['文件'] for v in rows]+[repo/'experiments/stereo_drive_v1/checks.c',Path(__file__),
        repo/'research/stereo_drive_v1_plan.json',repo/'tools/snapshot_stereo_drive_v1.py',
        repo/'handoff/CMakeLists.txt',repo/'Launch-Stereo-Drive-Study.cmd']+list((repo/'modules').rglob('CMakeLists.txt'))
    for path in paths:
        name=path.relative_to(repo).as_posix();target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['sources'][name]=sha(path)
    prior=json.loads((repo/'research/stereo_resonance_v1_summary.json').read_text(encoding='utf-8'))
    assert sha(repo/prior['profile_path'])==prior['profile_sha256']
    r['inputs']={v.relative_to(repo).as_posix():sha(v) for v in (repo/'voices').rglob('*') if v.is_file() and v.suffix in ('.model','.rdetail','.sres','.residual','.start','.cb')}
    reused=None
    if a.reuse:
        reused=json.loads((a.reuse/'report.json').read_text(encoding='utf-8'))
        for name,digest in reused['sources'].items():
            if name!='tools/verify_stereo_drive_v1.py':assert sha(repo/name)==digest,name
        for name,digest in reused['evidence_sha256'].items():assert sha(a.reuse/name)==digest,name
        assert sha(a.build/'CMakeCache.txt')==reused['evidence_sha256']['CMakeCache.after_build.txt']
        assert reused['commands'][0]['exit']==0
        full=(a.reuse/reused['commands'][0]['log']).read_bytes()
        shutil.copy2(a.reuse/reused['commands'][0]['log'],a.out/'reused_ctest.log')
        r['reused_proof']=dict(report=str(a.reuse/'report.json'),sha256=sha(a.reuse/'report.json'),runtime_sources_exact=True)
    else:full=run(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'],timeout=600)
    assert re.search(rb'100% tests passed(?:, 0 tests failed)? out of 53',full);r['Ctests_passed']=53
    shutil.copy2(a.build/'CMakeCache.txt',a.out/'CMakeCache.after_build.txt')
    (a.out/'bin').mkdir()
    for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslDriveResonance_device','VslAtlasMonitor'):
        shutil.copy2(a.build/'bin/Release'/f'{name}.exe',a.out/'bin'/f'{name}.exe')
    zero=a.workspace/'references/analysis/drive_resonance_v1/before1'
    cases=json.loads((zero/'snapshot.json').read_text(encoding='utf-8'))['cases'];renders=a.out/'renders'
    if reused:shutil.copytree(a.reuse/'renders',renders)
    else:renders.mkdir()
    for case in cases:
        opts=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        if not reused:run([a.out/'bin/VslAtlasDrive_probe.exe',*case['models'][:2],renders/case['name'],*opts])
        files=list((zero/'renders').glob(case['name']+'_*.wav'));assert len(files)==28
        for path in files:assert path.read_bytes()==(renders/path.name).read_bytes(),path.name
        trace=case['name']+'_trace.csv';assert (zero/'renders'/trace).read_bytes()==(renders/trace).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_bytes_equal=len(files),trace_exact=True))
    for name,opts,frames in (('rdt_bench',[],144123),('stereo_bench',['--stereo'],144123),('stereo_pedals',['--stereo','--pedals'],768123)):
        folder=a.out/name;reuse_device=bool(reused and name=='rdt_bench')
        if reuse_device:shutil.copytree(a.reuse/name,folder)
        else:folder.mkdir();run([a.out/'bin/VslDriveResonance_device.exe',folder,*opts])
        d=json.loads((folder/'device.json').read_text());state=json.loads((folder/'state_inspection.json').read_text())
        assert d['result']=='pass' and d['schema']==7 and d['fields']==28 and d['frames']==frames
        assert d['record_hash']==d['play_hash']==state['output_hash']
        assert d['record_queue_empty']==d['play_queue_empty']==0
        assert d['stereo_kernel']==name.startswith('stereo')
        recorded,rate=sf.read(folder/'recorded.wav',always_2d=True)
        inspected,rate2=sf.read(folder/'inspected.wav',always_2d=True)
        assert rate==rate2==48000 and np.array_equal(recorded,inspected)
        take=folder/'detail_schema7.vslrun';assert int.from_bytes(take.read_bytes()[8:12],'little')==7
        exports=[]
        for channels in (2,12):
            out=folder/f'export_{channels}.wav'
            if reuse_device:
                row=json.loads((a.reuse/reused['commands'][5 if channels==2 else 6]['log']).read_text(encoding='utf-8'))
            else:row=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',take,out,'--channels',channels]))
            assert row['verified'];exports.append(row)
        two,_=sf.read(folder/'export_2.wav',always_2d=True);twelve,_=sf.read(folder/'export_12.wav',always_2d=True)
        assert np.array_equal(two,recorded) and np.array_equal(twelve[:,:2],two) and np.count_nonzero(twelve[:,2:])==0
        assert exports[0]['source_hash']==exports[1]['source_hash']==state['source_hash']
        trace=np.genfromtxt(folder/'pedal_trace.csv',delimiter=',',names=True)
        roots=trace['root_hz'];base=34.837537335058876 if name.startswith('stereo') else 10.005674
        # Read the authoritative base from the preserved pure parameter input.
        profile=repo/('voices/stereo_resonance_v1/A cabin settle.sres' if name.startswith('stereo') else 'voices/resonant_detail_c_v1/idle_add.rdetail')
        base=float(profile.read_text().splitlines()[0].split()[-1]);x=roots/base
        expected=np.zeros_like(x);expected[(x>=.96)&(x<=1.04)]=1
        lo=(x>.9)&(x<.96);hi=(x>1.04)&(x<1.1)
        u=(x[lo]-.9)/(.96-.9);expected[lo]=u*u*(3-2*u)
        u=(1.1-x[hi])/(1.1-1.04);expected[hi]=u*u*(3-2*u)
        expected*=expected  # DrsFrame.support is the sum of squared mixture weights.
        # rdt_bench has four DNA anchors; only anchor0 has detail, and its
        # sqrt blend weight is also present in the support sum.
        if name=='rdt_bench':expected*=np.where(trace['lower']==trace['upper'],(trace['lower']==0),np.where(trace['lower']==0,1-trace['blend'],0))
        error=float(abs(expected-trace['resonant_support']).max());assert error<1e-12,error
        detail,_=sf.read(folder/'detail_stem.wav',always_2d=True);assert np.isfinite(detail).all() and np.any(detail!=0)
        for row in trace:
            if row['resonant_support']==0:assert np.array_equal(detail[int(row['frame'])],[0,0])
        if name=='stereo_pedals':
            assert all(v['mode']==1 for v in d['controls'])
            for st in ('IDLE','PULL','SHIFT CUT','OVERRUN','REV MATCH'):assert state['running_operating'][st]['frames']>0,st
            assert state['running_operating']['IDLE']['detail_supported_frames']>0
            assert state['lifecycle']['OFF']['frames']>0 and max(trace['rpm'])>5000
        r['devices'][name]=dict(device=d,state=state,exports=exports,source_and_front_2_12_exact=True,scalar_support_max_error=error)
    run([a.out/'bin/VslAtlasTake_render.exe',before/'device/detail_schema6.vslrun',a.out/'reject_schema6.wav'],expected=3)
    run([before/'VslAtlasTake_render.exe',a.out/'stereo_bench/detail_schema7.vslrun',a.out/'reject_schema7.wav'],expected=3)
    assert not (a.out/'reject_schema6.wav').exists() and not (a.out/'reject_schema7.wav').exists()
    r['ui']={}
    for flag in ('--resonant-study','--stereo-resonant-study'):
        folder=a.out/flag[2:];folder.mkdir();run([a.out/'bin/VslAtlasMonitor.exe',flag,'--ui-check',folder/'ui.json'])
        u=json.loads((folder/'ui.json').read_text());assert u['result']=='pass'
        Image.open(folder/'ui.json.bmp').convert('RGB').save(folder/'window.png');r['ui'][flag]=u
    r.update(result='stereo_driver_technical_pass',prior_C_H=529,unchanged_prior_C_H=519,new_C_H=1,C_H_rows=530,
        schema=7,fields=28,parameters_unchanged=True,new_listening_acceptance=False,full_idle_or_acceleration_calibrated=False,
        limits=['Cabin startup-settling context only; engineering850 mapping is not a measured idle target',
                'Local .9..1.1 support is not full RPM/load coverage; moving35 full replacement remains separate',
                'No physical crank or load calibration, new room model or stereo-source isolation',
                'Short muted device/own UI controls, not longrun/manual mouse/physical7.1.4 acceptance'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:
    r['evidence_sha256']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file() and 'exact_sources' not in v.parts}
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
