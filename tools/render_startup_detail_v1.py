"""Exercise a fitted detail model using unchanged unified C libraries."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from startup_detail_v1.budget import errors,BANDS
from residual_osc_v1.spectrum import matrices

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],human_accepted=False,device_checked=False)
def run(cmd):
    cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:4])),flush=True)
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=600)
    path=a.out/f'command_{len(r["commands"]):02}.log';path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,exit_code=done.returncode,log=path.name,sha256=sha(path)))
    assert done.returncode==0,path.name

try:
    fitroot=a.workspace/'references/analysis/startup_detail_v1/fit1'
    fit=json.loads((fitroot/'report.json').read_text(encoding='utf-8'))
    assert fit['result']=='same_A_additive_stereo_candidate_fitted'
    model=fitroot/fit['profile']['file'];assert sha(model)==fit['profile']['sha256']
    r['fit_report_sha256']=sha(fitroot/'report.json')
    # Bind the pre-stage index, so adding this experiment to the live index
    # does not make its own reproduction fail.
    frozen=a.workspace/'baselines/catch_drive_v1'
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    index_path=frozen/'docs/handoff/C文件索引.csv'
    assert sha(index_path)==next(v['sha256'] for v in manifest['files'] if v['path']=='docs/handoff/C文件索引.csv')
    with index_path.open(encoding='utf-8-sig') as stream:old=list(csv.DictReader(stream))
    assert len(old)==468
    for row in old:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    shutil.copy2(index_path,a.out/'before_C文件索引.csv')
    paths=[Path(__file__),repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt']
    for folder in ('src','modules','experiments'):
        paths.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
    paths.extend((repo/'tools/startup_detail_v1').glob('*.py'))
    r['source_sha256']={}
    for path in paths:
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['source_sha256'][name]=sha(path)
    build=repo/'build-startup-detail-v1'
    run(['cmake','-S',repo/'experiments/startup_detail_v1','-B',build,'-A','x64'])
    run(['cmake','--build',build,'--config','Release','--target','startup_detail_probe','--parallel','4'])
    (a.out/'bin').mkdir();probe=a.out/'bin/startup_detail_probe.exe';shutil.copy2(build/'Release/startup_detail_probe.exe',probe)
    r['binary_sha256']=sha(probe)
    dna=repo/'voices/startup_settle_v1/A start cabin settle.model'
    starter=repo/'voices/startup_drive_v1/A cabin motion.start';catch=repo/'voices/catch_bloom_v1/A cabin catch.cb'
    assert sha(dna)==fit['DNA_sha256']
    r['model_sha256']={str(x.relative_to(repo)):sha(x) for x in (dna,starter,catch)}
    (a.out/'renders').mkdir()
    def render(key,amount,channels,mode,seed):
        run([probe,dna,starter,catch,model,a.out/'renders'/key,amount,channels,mode,seed])
    for channels in (2,12):
        for amount in (0,.5,1):render(f'starts_{channels}_{amount:.1f}',amount,channels,'starts',48271)
    for seed in (48271,62017,91009):
        for amount in (0,1):render(f'hold_{seed}_{amount}',amount,2,'hold',seed)
    def audio(key,stem):
        y,rate=sf.read(a.out/'renders'/f'{key}_{stem}.wav',always_2d=True)
        assert rate==48000 and np.isfinite(y).all();return y
    # An added, silent residual model must preserve the previous entire scene.
    oldroot=a.workspace/'references/analysis/catch_drive_v1/verification1/renders'
    for stem in ('mix','raw','dna','startup','catch_bloom','trace'):
        ext='csv' if stem=='trace' else 'wav'
        assert (a.out/'renders'/f'starts_2_0.0_{stem}.{ext}').read_bytes()==(oldroot/f'catch_2_0.5_{stem}.{ext}').read_bytes(),stem
    r['old_scene_six_files_byte_equal']=True
    r['integration']=[]
    for amount in (0,.5,1):
        key=f'starts_2_{amount:.1f}';front=audio(key,'mix');surround=audio(f'starts_12_{amount:.1f}','mix')
        assert np.array_equal(front,surround[:,:2]) and np.max(abs(surround[:,2:]))==0
        expected=.25*sum(audio(key,s) for s in ('dna','startup','catch_bloom','residual'))
        error=float(np.max(abs(front-expected)));assert error<2e-8
        for stem in ('raw','dna','startup','catch_bloom','residual_raw','trace'):
            ext='csv' if stem=='trace' else 'wav'
            assert (a.out/'renders'/f'{key}_{stem}.{ext}').read_bytes()==(a.out/'renders'/f'starts_2_0.0_{stem}.{ext}').read_bytes(),stem
            assert (a.out/'renders'/f'{key}_{stem}.{ext}').read_bytes()==(a.out/'renders'/f'starts_12_{amount:.1f}_{stem}.{ext}').read_bytes(),stem
        r['integration'].append(dict(amount=amount,single_mix_error=error,front_equal=True,other10_zero=True))
    target,_=sf.read(fitroot/'reference_float.wav',always_2d=True)
    r['hold']=[]
    for seed in (48271,62017,91009):
        base=audio(f'hold_{seed}_0','raw')[96000:];cloud=audio(f'hold_{seed}_1','residual_raw')[96000:]
        # Compare un-enveloped source units, not master/envelope level differences.
        combo=base+cloud;old_errors=errors(target,base);new_errors=errors(target,combo)
        active=[v['accepted'] for v in fit['rows']]
        before=np.array([v['LR_dB'] for v in old_errors]);after=np.array([v['LR_dB'] for v in new_errors])
        r['hold'].append(dict(seed=seed,baseline=old_errors,candidate=new_errors,
            active_mean_absolute_dB_before=float(np.mean(abs(before[active]))),
            active_mean_absolute_dB_after=float(np.mean(abs(after[active]))),
            active_maximum_absolute_dB_after=float(np.max(abs(after[active]))),
            max_active_coherence_error=float(max(v['coherence_error'] for v,m in zip(new_errors,active) if m))))
    r.update(result='unified_C_detail_candidate_rendered',prior468_C_H_unchanged=True,
        old45_CTests_not_repeated=True,new_C_H=['experiments/startup_detail_v1/probe.c'],
        limits=['Offline source and integration checks only; no new device/UI/take integration or listening acceptance',
                'Measured mean stereo statistics are not perceived naturalness; incomplete600–850Hz and fast catch retained'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],integration=r.get('integration'),hold=[{k:v for k,v in row.items() if k not in ('baseline','candidate')} for row in r.get('hold',[])])))
