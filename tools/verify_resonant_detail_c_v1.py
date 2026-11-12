"""Build modular C detail, run contracts, compare exact seeds with Python DSP."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--contract-proof',type=Path,help='Reuse unchanged build and the actual48-pass CTest log')
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from resonant_detail_v1.voice import render

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.resonant-detail-c-verification/1',result='running',source_sha256={},input_sha256={},commands=[],comparisons=[])

def command(argv,expected=0):
    started=time.perf_counter()
    done=subprocess.run([str(v) for v in argv],cwd=repo,capture_output=True,timeout=60 if str(argv[0])!='ctest' else 120)
    file=a.out/f'command_{len(r["commands"]):02d}.log';file.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=[str(v) for v in argv],exit_code=done.returncode,
        wall_seconds=time.perf_counter()-started,log=file.name,sha256=sha(file)))
    assert done.returncode==expected,(argv,done.returncode,file)
    return done

try:
    index=repo/'handoff/C文件索引.csv'
    shutil.copy2(index,a.out/'prior_C_index.csv')
    r['input_sha256'][str(a.out/'prior_C_index.csv')]=sha(index)
    with index.open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
    existing=[v for v in prior if not v['文件'].startswith(('modules/resonant_detail/','modules/resonant_detail_io/','experiments/resonant_detail_c_v1/'))]
    assert len(existing)==478
    for row in existing:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    paths=[Path(__file__),repo/'handoff/CMakeLists.txt',repo/'tools/export_resonant_detail_c_v1.py',
        repo/'tools/resonant_detail_v1/voice.py',repo/'tools/resonant_detail_v1/envelope.py',repo/'tools/sustain_osc_v1/oracle.py',
        repo/'modules/residual_dense/CMakeLists.txt']
    for folder in ('modules/resonant_detail','modules/resonant_detail_io','experiments/resonant_detail_c_v1'):
        paths.extend(p for p in (repo/folder).iterdir() if p.is_file())
    for path in paths:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    r['pre_build_CMakeCache_sha256']=sha(a.build/'CMakeCache.txt')
    pattern=rb'100% tests passed(?:, 0 tests failed)? out of 48'
    if a.contract_proof:
        proof=json.loads(a.contract_proof.read_text(encoding='utf-8'))
        for name,digest in proof['source_sha256'].items():
            if name!=Path(__file__).relative_to(repo).as_posix():assert sha(repo/name)==digest,name
        for row in proof['commands']:
            file=a.contract_proof.parent/row['log'];assert sha(file)==row['sha256']
            if row['argv'][0] in ('cmake','ctest'):
                assert row['exit_code']==0
                shutil.copy2(file,a.out/('reused_'+row['log']))
        test=next(v for v in proof['commands'] if v['argv'][0]=='ctest')
        assert re.search(pattern,(a.contract_proof.parent/test['log']).read_bytes())
        r['reused_contract_proof']=dict(file=str(a.contract_proof),sha256=sha(a.contract_proof),Ctests=48)
    else:
        command(['cmake','--build',a.build,'--config','Release','--parallel','4'])
        done=command(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'])
        assert re.search(pattern,done.stdout)
    r['Ctests_passed']=48
    # cmake --build may regenerate the cache; bind the configuration actually tested.
    r['input_sha256'][str(a.build/'CMakeCache.txt')]=sha(a.build/'CMakeCache.txt')
    shutil.copy2(a.build/'CMakeCache.txt',a.out/'CMakeCache.after_build.txt')
    probe=a.build/'bin/Release/VslResonantDetail_probe.exe'
    shutil.copy2(probe,a.out/probe.name);probe=a.out/probe.name
    r['probe_sha256']=sha(probe)
    index_path=repo/'voices/resonant_detail_c_v1/index.json'
    export=json.loads(index_path.read_text(encoding='utf-8'))
    r['input_sha256'][str(index_path)]=sha(index_path)
    raw=a.out/'raw';raw.mkdir()
    for profile in export['profiles']:
        path=repo/profile['file'];source=repo/profile['original']
        assert sha(path)==profile['sha256'] and sha(source)==profile['original_sha256']
        r['input_sha256'].update({str(path):sha(path),str(source):sha(source)})
        model=json.loads(source.read_text(encoding='utf-8'))
        ratios=np.asarray(model['kernel'].get('stereo_R_over_L',model.get('stereo_R_over_L')))
        choice=next(v for v in model['presets'] if v['name']==profile['preset'])
        gain=np.asarray(choice.get('detail_amplitude_gain',choice.get('detail_gain')))
        plan=dict(warmup_frames=model['kernel']['warmup_frames'],cycle_frames=model['kernel']['cycle_frames'])
        warm=plan['warmup_frames'];frames=96000
        start=-warm*model['acoustic_root_hz']/48000
        for seed in (8121907,23117,61927):
            file=raw/f'{profile["name"]}_{seed}.f64'
            command([probe,path,file,warm+frames,seed,start])
            data=np.fromfile(file,dtype='<f8').reshape(warm+frames,profile['bands']+2)
            assert np.isfinite(data).all()
            expected=render(model['filters'],frames,seed,plan)
            actual=data[warm:,2:]
            band_errors=abs(actual-expected).max(axis=0)
            stereo=np.column_stack((expected@gain,expected@(gain*ratios)))
            stereo_error=float(abs(data[warm:,:2]-stereo).max())
            assert band_errors.max()<1e-7 and stereo_error<1e-9,(profile['name'],seed,band_errors,stereo_error)
            r['comparisons'].append(dict(profile=profile['name'],seed=seed,frames=frames,warmup_frames=warm,
                max_unit_band_error=band_errors.tolist(),max_stereo_error_FS=stereo_error,
                relative_band_error=float(np.sqrt(np.mean((actual-expected)**2))/np.sqrt(np.mean(expected**2))),
                output_file=file.relative_to(a.out).as_posix(),output_sha256=sha(file)))
            print(json.dumps(dict(profile=profile['name'],seed=seed,band_error=float(max(band_errors)),stereo_error=stereo_error)),flush=True)
    # File-level rejection uses the actual C loader and proves no output opened.
    invalid=a.out/'invalid';invalid.mkdir()
    valid=(repo/export['profiles'][0]['file']).read_text(encoding='ascii')
    cases=[valid.replace('VSL_RESONANT_DETAIL','FOREIGN',1),valid+'trailing\n',
           'VSL_RESONANT_DETAIL 1 48000 99 0 40\n',valid[:80],
           valid.replace('0.013240500942305661','nan',1)]
    # Guaranteed NaN even if textual formatting changes in a later export.
    words=valid.split();words[12]='nan';cases[-1]=' '.join(words)+'\n'
    for i,text in enumerate(cases):
        path=invalid/f'{i}.rdetail';path.write_text(text,encoding='ascii')
        output=invalid/f'{i}.f64';command([probe,path,output,1,71,0],expected=2)
        assert not output.exists()
    r.update(result='C_kernel_and_cross_language_parity_pass',prior_C_H_unchanged=478,new_C_H=14,
        invalid_files_rejected_before_output=len(cases),new_timbre_fitting=False,
        source_clock_owned_by_caller=True,driver_UI_default_take_changed=False,
        native_listening_or_device_acceptance=False,
        limits=['C kernel only: no full mixture/native UI/driver/take adapter or new timbre acceptance',
            'Same existing parameters and random streams; parity is not a new naturalness rating',
            'Fixed-Hz resonators are source-context parameters, not a calibrated fullRPM/load map',
            'Rank-one detail L/R ratios are observation transfer, not engine banks or speaker positions',
            'All48Ctests are contracts; no callback budget,longrun or physical7.1.4 claim'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],comparisons=len(r['comparisons']),Ctests=r.get('Ctests_passed'))))
