"""Verify full moving35 in the one-driver/native/owned-recording path."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','build','build-proof','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from PIL import Image
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
r=dict(schema='vsl.full-recipe-drive-verification/1',result='running',commands=[],devices={},legacy=[],ui={})
def run(argv,expected=0,timeout=150):
    started=time.perf_counter();proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=timeout)
    log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit=proc.returncode,expected=expected,seconds=time.perf_counter()-started,log=log.name,sha256=sha(log)))
    print(json.dumps(dict(command=str(argv[0]),exit=proc.returncode,log=str(log))),flush=True)
    assert proc.returncode==expected,(argv,log);return proc.stdout
try:
    b=json.loads((a.build_proof/'report.json').read_text(encoding='utf-8'))
    assert b['result']=='passed' and b['stage']=='all'
    for name,digest in b['sources'].items():assert sha(repo/name)==digest==sha(a.build_proof/'exact_sources'/name),name
    for command in b['commands']:assert command['exit_code']==0 and sha(a.build_proof/command['log'])==command['sha256']
    full=(a.build_proof/b['commands'][-1]['log']).read_bytes();assert re.search(rb'100% tests passed(?:, 0 tests failed)? out of 55',full)
    assert sha(a.build/'CMakeCache.txt')==b['cache_sha256']
    r.update(build_proof_sha256=sha(a.build_proof/'report.json'),Ctests_passed=55,sources=b['sources'])
    shutil.copy2(__file__,a.out/'executed_verify.py')
    before=a.workspace/'references/analysis/full_recipe_drive_v1/before1'
    previous=json.loads((before/'report.json').read_text(encoding='utf-8'));assert previous['result']=='verified_old_player_preserved'
    for name,digest in previous['files'].items():assert sha(before/name)==digest,name
    for name,digest in previous['voices'].items():assert sha(repo/name)==digest,name
    r['unchanged_voices']=previous['voices'];r['before_sha256']=sha(before/'report.json')
    r['modified_prior_C_H']=[name for name,digest in previous['C_H'].items() if sha(repo/name)!=digest]
    r['new_C_H']=[name for name in b['sources'] if Path(name).suffix.lower() in ('.c','.h') and name not in previous['C_H']]
    (a.out/'bin').mkdir()
    for name in ('VslAtlasDrive_probe','VslAtlasTake_render','VslDriveResonance_device','VslAtlasMonitor'):
        shutil.copy2(a.build/'bin/Release'/f'{name}.exe',a.out/'bin'/f'{name}.exe')
    old=a.workspace/'references/analysis/drive_resonance_v1/before1'
    cases=json.loads((old/'snapshot.json').read_text(encoding='utf-8'))['cases'];renders=a.out/'renders';renders.mkdir()
    for case in cases:
        options=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        run([a.out/'bin/VslAtlasDrive_probe.exe',*case['models'][:2],renders/case['name'],*options])
        paths=list((old/'renders').glob(case['name']+'_*.wav'));assert len(paths)==28
        for path in paths:assert path.read_bytes()==(renders/path.name).read_bytes(),path.name
        trace=case['name']+'_trace.csv';assert (old/'renders'/trace).read_bytes()==(renders/trace).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_bytes_equal=len(paths),trace_exact=True))
    for name,opts,frames in (('full_bench',['--full'],144123),('full_pedals',['--full','--pedals'],768123),('legacy_stereo_bench',['--stereo'],144123)):
        folder=a.out/name;folder.mkdir();run([a.out/'bin/VslDriveResonance_device.exe',folder,*opts])
        d=json.loads((folder/'device.json').read_text());state=json.loads((folder/'state_inspection.json').read_text())
        assert d['result']=='pass' and d['schema']==8 and d['fields']==29 and d['frames']==frames
        assert d['record_hash']==d['play_hash']==state['output_hash']
        assert d['record_queue_empty']==d['play_queue_empty']==d['record_budget_exceeded']==d['play_budget_exceeded']==0
        assert d['full_recipe']==name.startswith('full') and d['owned_models_destroyed_before_replay']
        recorded,rate=sf.read(folder/'recorded.wav',always_2d=True);inspected,rate2=sf.read(folder/'inspected.wav',always_2d=True)
        assert rate==rate2==48000 and np.array_equal(recorded,inspected)
        take=folder/'detail_schema8.vslrun';header=take.read_bytes()[:80]
        assert int.from_bytes(header[8:12],'little')==8 and int.from_bytes(header[76:80],'little')==29
        exports=[]
        for channels in (2,12):
            row=json.loads(run([a.out/'bin/VslAtlasTake_render.exe',take,folder/f'export_{channels}.wav','--channels',channels]));assert row['verified'];exports.append(row)
        two,_=sf.read(folder/'export_2.wav',always_2d=True);twelve,_=sf.read(folder/'export_12.wav',always_2d=True)
        assert np.array_equal(recorded,two) and np.array_equal(twelve[:,:2],two) and np.count_nonzero(twelve[:,2:])==0
        assert exports[0]['source_hash']==exports[1]['source_hash']==state['source_hash']
        trace=np.genfromtxt(folder/'pedal_trace.csv',delimiter=',',names=True)
        low,_=sf.read(folder/'coherent_low_stem.wav',always_2d=True);detail,_=sf.read(folder/'detail_stem.wav',always_2d=True)
        dna,_=sf.read(folder/'dna_stem.wav',always_2d=True);lowraw,_=sf.read(folder/'coherent_low_raw.wav',always_2d=True)
        assert all(np.isfinite(v).all() for v in (low,detail,dna,lowraw))
        error=0.
        if name.startswith('full'):
            x=trace['root_hz']/46.875;expected=np.zeros_like(x);expected[(x>=.96)&(x<=1.04)]=1
            mask=(x>.9)&(x<.96);u=(x[mask]-.9)/.06;expected[mask]=u*u*(3-2*u)
            mask=(x>1.04)&(x<1.1);u=(1.1-x[mask])/.06;expected[mask]=u*u*(3-2*u)
            expected*=expected
            error=float(max(abs(expected-trace['resonant_support']).max(),abs(expected-trace['coherent_low_support']).max()));assert error<1e-12,error
            assert np.any(low!=0) and np.any(detail!=0)
            for row in trace:
                frame=int(row['frame'])
                if row['coherent_low_support']==0:assert np.array_equal(low[frame],[0,0]) and np.array_equal(lowraw[frame],[0,0])
                if row['resonant_support']==0:assert np.array_equal(detail[frame],[0,0])
            if name=='full_pedals':
                assert all(v['mode']==1 for v in d['controls'])
                for state_name in ('IDLE','PULL','SHIFT CUT','OVERRUN','REV MATCH'):assert state['running_operating'][state_name]['frames']>0,state_name
                assert state['running_operating']['IDLE']['low_supported_frames']==0
        else:assert np.count_nonzero(low)==np.count_nonzero(lowraw)==0
        r['devices'][name]=dict(device=d,state=state,exports=exports,source_and_front_2_12_exact=True,scalar_support_max_error=error)
    run([a.out/'bin/VslAtlasTake_render.exe',before/'device_schema7.vslrun',a.out/'reject_schema7.wav'],expected=3)
    run([before/'VslAtlasTake_render.exe',a.out/'full_bench/detail_schema8.vslrun',a.out/'reject_schema8.wav'],expected=3)
    assert not (a.out/'reject_schema7.wav').exists() and not (a.out/'reject_schema8.wav').exists()
    for flag in ('--full-recipe-study','--resonant-study','--stereo-resonant-study'):
        folder=a.out/flag[2:];folder.mkdir();run([a.out/'bin/VslAtlasMonitor.exe',flag,'--ui-check',folder/'ui.json'])
        u=json.loads((folder/'ui.json').read_text());assert u['result']=='pass'
        Image.open(folder/'ui.json.bmp').convert('RGB').save(folder/'window.png');r['ui'][flag]=u
    r.update(result='full_recipe_driver_technical_pass',schema_version=8,control_fields=29,
        driver_integrated=True,native_integrated=True,owned_take_integrated=True,models_unchanged=True,
        new_listening_acceptance=False,full_idle_or_acceleration_calibrated=False,
        limits=['Retained moving35 recipe has one local acoustic anchor, not full RPM/load coverage',
                'Engine RPM mapping 1/120 and support fades are engineering assumptions, not ECU measurements',
                'Stable controller idle is outside this moving recipe support; no fabricated idle timbre coverage',
                'No new room/deconvolution/physical source separation, physical 7.1.4 or long-run/manual-mouse acceptance'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:
    r['evidence_sha256']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file()}
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
