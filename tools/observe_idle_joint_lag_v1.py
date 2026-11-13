"""All source/phase/current0and100 windows on a fixed lag observation grid."""
import argparse,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_joint_cumulant_v1.moments import local_normalize
from idle_joint_lag_v1.observe import curves,correlation,support,summarize,PAIRS
from idle_joint_lag_v1.checks import run

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_manifests={},inputs={},observations=[])
try:
    path=repo/'research/idle_joint_lag_v1_plan.json';plan=load(path)
    for path in [Path(__file__),path,repo/'tools/research_archive_v1.py',repo/'tools/idle_joint_cumulant_v1/moments.py',
                 *sorted((repo/'tools/idle_joint_lag_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    lags=np.arange(-1920,1921,48)
    known=a.out/'known';known.mkdir();r['known']=run(known,lags)
    print(dict(stage='known_controls',result=r['known']),flush=True)
    parents={}
    for name in ['idle_joint_cumulant_v1','idle_excitation_moments_v1']:
        root=a.workspace/'baselines'/name;manifest=load(root/'manifest.json')
        parents[name]=(root,{v['path']:v['sha256'] for v in manifest['files']})
        r['parent_manifests'][name]=sha(root/'manifest.json')
    def parent(name,file):
        root,table=parents[name];path=root/file;assert sha(path)==table[file]
        r['inputs'][str(path)]=table[file];return path
    base='idle_joint_cumulant_v1';prior=load(parent(base,'evidence/observe1/report.json'))
    architecture=np.load(parent(base,'evidence/observe1/architecture.npz'))
    sos=architecture['sos'];cache_path=None;cache=None;main_K=None
    for old in prior['observations']:
        if old['kind']=='conditioned50' or (old['kind']=='sparse' and old['amount']==.5):continue
        if old['kind']=='source':
            path=parent('idle_excitation_moments_v1','evidence/observe1/'+old['label']+'.npz')
            with np.load(path) as data:audio=data['audio']
            filtered=np.column_stack([signal.sosfilt(s,audio[:,0]) for s in sos])[4800:-4800]
            provenance=dict(source_npz=str(path))
        elif old['kind']=='phase':
            path=parent(base,'evidence/observe1/'+old['control'])
            with np.load(path) as data:audio=data['audio']
            filtered=np.column_stack([signal.sosfilt(s,audio[:,0]) for s in sos])[4800:-4800]
            provenance=dict(source_npz=str(path))
        elif old['kind']=='main':
            filtered=np.column_stack([signal.sosfilt(s,architecture['main'][:,0]) for s in sos])[4800:-4800]
            provenance=dict(main=True)
        else:
            relative=Path(old['path']).relative_to(a.workspace/'baselines/idle_excitation_moments_v1').as_posix()
            path=parent('idle_excitation_moments_v1',relative)
            if cache_path!=str(path):
                audio,rate=sf.read(path,always_2d=True);assert rate==48000 and len(audio)==576000
                cache=np.column_stack([signal.sosfilt(s,audio[:,0]) for s in sos]);cache_path=str(path)
            filtered=cache[old['block']*144000+4800:(old['block']+1)*144000-4800]
            provenance=dict(path=str(path),block=old['block'])
        row={key:old[key] for key in ['label','kind','amount','seed','portion','block'] if key in old}
        row.update(provenance);row['summary']={}
        arrays=dict(lags=lags)
        for transform,x in [('raw',filtered),('local40ms',local_normalize(filtered,1920))]:
            result=curves(x,lags)
            for key,value in result.items():arrays[transform+'_'+key]=value
            zero=result['normalized'][:,40]
            expected=np.array([old[transform]['normalized'][b][c] for b,c in PAIRS])
            assert np.allclose(zero,expected,atol=1e-9),(old['label'],transform)
            row['summary'][transform]=summarize(result['normalized'],lags)
            if old['kind']=='main' and transform=='raw':main_K=result['cumulant']
        filename=old['label']+'.npz';np.savez_compressed(a.out/filename,**arrays)
        row['file']=filename;row['sha256']=sha(a.out/filename);r['observations'].append(row)
        if len(r['observations'])%8==0:print(dict(stage='observations',done=len(r['observations'])),flush=True)
    h=architecture['responses'];kappa=architecture['kappa'];variance=architecture['variance']
    expectation=[]
    for b,c in PAIRS:
        values=sum(kappa[i]*correlation(h[b,i]**2,h[c,i]**2,lags) for i in range(6))
        expectation.append(values)
    expectation=np.array(expectation)
    total=expectation+main_K
    normalized=np.array([total[j]/variance[b]/variance[c] for j,(b,c) in enumerate(PAIRS)])
    assert np.allclose(normalized[:,40],[prior['theoretical_raw']['1'][b][c] for b,c in PAIRS],atol=1e-9)
    np.savez_compressed(a.out/'expectation.npz',lags=lags,independent_cumulant=expectation,
        with_main_cumulant=total,normalized=normalized,h=h,kappa=kappa,variance=variance)
    r.update(result='all33_idle_lag_observations_complete_NO_sound_promotion',plan=plan,
        response_support=support(h),expectation_summary=summarize(normalized,lags),new_audio_or_profile=False,runtime_changed=False)
    assert len(r['observations'])==33
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
