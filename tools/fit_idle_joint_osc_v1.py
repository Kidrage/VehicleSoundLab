"""Qualify and fit joint OSC coefficients before deciding on finite generation."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_joint_osc_v1.kernel import known as kernel_known
from idle_joint_osc_v1.moment import known as moment_known,compile_model,independent_blocks
from idle_joint_osc_v1.analysis import observe,BANDS

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},observations=[])
def input_path(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/fit_idle_joint_osc_v1.py','research/idle_joint_osc_v1_plan.json','tools/research_archive_v1.py',
        'tools/idle_phase_difference_v1/features.py','tools/idle_positive_power_v1/model.py']
    names += [p.relative_to(repo).as_posix() for p in (repo/'tools/idle_joint_osc_v1').glob('*.py')]
    for name in names:
        path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,path);r['sources'][name]=sha(repo/name)
    parent=a.workspace/'baselines';phase=load(input_path(parent/'idle_phase_recipe_v1/evidence/render2/model.json'))
    spacing=phase['carrier_hz'];r['known'],native,node=kernel_known(spacing);r['known']['moment']=moment_known()
    print(dict(stage='known',known=r['known']),flush=True)
    harmonics=np.arange(int(np.ceil(1200/spacing)),int(np.floor(14000/spacing))+1)
    groups=np.searchsorted([2200,4000,8000],harmonics*spacing)
    law=load(input_path(parent/'idle_positive_power_v1/evidence/observe1/report.json'))['observations'][0]['models']['expanded']
    profile=load(input_path(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    target=[k['gain']**2*float(np.dot(k['taps'],k['taps'])) for k in profile['kernels'][2:]]
    origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    for seed in [None,149921,277139,381611]:
        arrays={};stats={}
        for part in ['train','check']:
            with np.load(input_path(origin/(part+'.npz'))) as f:audio=f['audio'];z=f['phasors']
            if seed is not None:
                spectrum=np.fft.rfft(audio,axis=0);angle=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(spectrum));angle[0]=angle[-1]=0
                audio=np.fft.irfft(spectrum*np.exp(1j*angle[:,None]),n=len(audio),axis=0)
                with np.load(input_path(origin/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            arrays[part],stats[part]=observe(audio,z,law,harmonics,groups,native)
            print(dict(stage='observed',seed=seed,part=part),flush=True)
        model,info=compile_model(arrays['train'],groups,target)
        scale=model['row_scale'];real=np.column_stack((arrays['check'].real,arrays['check'].imag))*scale
        check=real.T@real/len(real)
        norm=np.linalg.norm(check)
        comparison=dict(joint_relative_distance=float(np.linalg.norm(model['moment']-check)/norm),
            independent_relative_distance=float(np.linalg.norm(model['independent_moment']-check)/norm))
        label='source' if seed is None else 'phase_'+str(seed)
        path=a.out/(label+'.npz');np.savez_compressed(path,train=arrays['train'],check=arrays['check'],
            **model,check_moment=check,harmonics=harmonics,groups=groups,native_kernel=native,node_kernel=node)
        r['observations'].append(dict(seed=seed,file=path.name,sha256=sha(path),model=info,
            source_stats=stats,check=comparison))
        save(a.out/'report.json',r);print(dict(stage='model',seed=seed,comparison=comparison),flush=True)
    r.update(result='joint_osc_moment_fit_retained_pending_generation',spacing_hz=spacing,harmonics=harmonics.tolist(),
        groups=groups.tolist(),law=law,targets=target,source_recorded_trajectory_exported=False,
        check_used_for_fit=False,runtime_changed=False,physical_clock_identified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],models=len(r['observations'])),flush=True)
