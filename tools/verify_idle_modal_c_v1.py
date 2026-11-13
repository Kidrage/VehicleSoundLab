"""Build/test isolated C modes and compare every frozen Python seed."""
import argparse,json,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(a.workspace/'tools'/x) for x in ('ipm_deps','qp_deps','python_deps')]
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from idle_modal_v1.modal import render as modal_oracle
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},commands=[],comparisons=[],runtime_default_changed=False)
def command(label,cmd):
    start=time.perf_counter();done=subprocess.run(list(map(str,cmd)),cwd=repo,capture_output=True,timeout=180)
    file=a.out/(label+'.log');file.write_bytes(done.stdout+done.stderr)
    item=dict(label=label,command=list(map(str,cmd)),return_code=done.returncode,
        elapsed_seconds=time.perf_counter()-start,log_sha256=sha(file))
    r['commands'].append(item);save(a.out/'report.json',r);print(json.dumps(item),flush=True)
    if done.returncode:raise RuntimeError(f'{label} failed; see {file}')
    return done
try:
    files=[Path(__file__),repo/'tools/export_idle_modal_c_v1.py',repo/'research/idle_modal_c_v1_plan.json',
        repo/'tools/drive_evidence_v1/sources.py',repo/'tools/idle_modal_v1/modal.py']
    for folder in ['modules/modal_source','experiments/modal_idle_v1','modules/resonant_detail','modules/resonant_detail_io']:
        files.extend(path for path in (repo/folder).iterdir() if path.is_file())
    files.extend(repo/path for path in ['src/io/file.c','src/io/file.h','src/io/wav.c','src/io/wav.h'])
    for path in files:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    old=a.workspace/'baselines/idle_material_modal_v1'
    invariants={}
    for file in ['C_files_sha256.json','voice_files_sha256.json']:
        values=load(old/file);assert all(sha(repo/path)==digest for path,digest in values.items())
        invariants[file]=len(values)
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4';profile=load(parent/'profile.json')
    r['parent_profile_sha256']=sha(parent/'profile.json')
    freq=profile['modal']['frequencies_hz']
    r['fixed_parameter_phase_relations']=[dict(relation=label,difference_hz=difference,phase_drift12s_cycles=12*difference,
        meaning='Algebraic candidate property, not measured mechanical order or common clock') for label,difference in
        [('f3-f1-f2',freq[2]-freq[0]-freq[1]),('f6-2*f3',freq[5]-2*freq[2])]]
    build=repo/'build-modal-idle-v1'
    command('configure',['cmake','-S','experiments/modal_idle_v1','-B',build,'-A','x64'])
    command('build',['cmake','--build',build,'--config','Release','--parallel','2'])
    command('ctest',['ctest','--test-dir',build,'-C','Release','--output-on-failure','--output-junit',a.out/'ctest.xml'])
    xml=ET.parse(a.out/'ctest.xml').getroot();cases=xml.findall('.//testcase')
    assert len(cases)==2 and not xml.findall('.//failure') and not xml.findall('.//error')
    shutil.copy2(build/'CMakeCache.txt',a.out/'CMakeCache.txt')
    exe=build/'Release/modal_idle_probe.exe';r['binary_sha256']=sha(exe)
    modal_path=repo/'experiments/modal_idle_v1/F2_fixed_idle.msource'
    detail_path=repo/'experiments/modal_idle_v1/F2_fixed_idle.rdetail'
    for seed in [149921,277139,381611]:
        folder=a.out/str(seed);folder.mkdir();prefix=folder/'C'
        command(f'render_{seed}',[exe,modal_path,detail_path,prefix,12,seed,1,1])
        for stem,filename in [('modal','modal_only.wav'),('detail',f'detail_{seed}.wav'),('mix',f'mix_{seed}.wav')]:
            x,rate=sf.read(folder/f'C_{stem}.wav',always_2d=True)
            y,rate_y=sf.read(parent/filename,always_2d=True)
            assert rate==rate_y==48000 and x.shape==y.shape==(576000,2)
            error=float(abs(x-y).max());rms=float(np.sqrt(np.mean((x-y)**2)))
            r['comparisons'].append(dict(seed=seed,stem=stem,frames=len(x),maximum_FS_error=error,RMS_FS_error=rms,
                python_sha256=sha(parent/filename),C_sha256=sha(folder/f'C_{stem}.wav')))
            assert np.isfinite(x).all() and error<=1e-7,(seed,stem,error)
    for ratio in [.9,1.1]:
        folder=a.out/f'ratio_{ratio}';folder.mkdir();prefix=folder/'C'
        command(f'ratio_{ratio}',[exe,modal_path,detail_path,prefix,4,149921,ratio,0])
        x,rate=sf.read(folder/'C_modal.wav',always_2d=True)
        expected=modal_oracle(profile['modal'],len(x),48000,ratio)
        error=float(abs(x-expected).max());assert error<=1e-7 and rate==48000
        detail,rate=sf.read(folder/'C_detail.wav',always_2d=True);assert np.count_nonzero(detail)==0
        r['comparisons'].append(dict(ratio=ratio,stem='modal',frames=len(x),maximum_FS_error=error,detail_zero_exact=True))
    r.update(result='isolated_C_contracts_and_all_frozen_idle_samples_pass',CTest_count=2,
        old_invariants_unchanged=invariants,maximum_FS_error=max(v['maximum_FS_error'] for v in r['comparisons']),
        no_source_refitting=True,shared_engine_clock=False,native_driver_integrated=False,listening_accepted=False,
        limits=['Finite source/port tests, not hard-real-time or device/UI acceptance.',
            'Ratio adjusts modal frequencies only; measured resonators remain fixedHz.',
            'The independent-mode model can beat and does not define actual engine RPM/load or all-state transitions.'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],maximum_FS_error=r.get('maximum_FS_error'),tests=r.get('CTest_count'))),flush=True)
