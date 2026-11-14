"""Fit only TRAIN, save all checks, generate finite source-derived shape auditions."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_positive_power_v1.model import fit
from idle_shape_v1.split import known
from idle_shape_v1.analysis import observe,compile_model,assess_model
from idle_shape_v1.render import render

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},fits=[],renders=[])
def input_path(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/run_idle_shape_v1.py','research/idle_shape_v1_plan.json','tools/research_archive_v1.py',
        'tools/idle_phase_difference_v1/features.py','tools/idle_positive_power_v1/model.py',
        'tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_recipe_v1/render2.py',
        'tools/idle_phase_recipe_v1/spectral.py','tools/idle_modal_v1/modal.py']
    names += [p.relative_to(repo).as_posix() for p in (repo/'tools/idle_shape_v1').glob('*.py')]
    for name in names:
        target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target);r['sources'][name]=sha(repo/name)
    r['known']=known();print(dict(stage='known',result=r['known']),flush=True)
    # Source-independent exact positive law and a constant relative shape.
    t=np.arange(48000)/48000;z=np.exp(1j*(2*np.pi*t[:,None]*[71.3,119.7,203.1]+[.2,-.6,1.1]))
    from idle_phase_difference_v1.features import matrix
    feature=matrix(z,hop=1,trim=0);truth=np.zeros((13,8));truth[1]=np.arange(8)*.015;truth[8]=.04
    power=np.exp(truth[0]+feature@truth[1:]);model=fit(feature,power)
    expected=truth.copy();expected[0]-=np.log(power.mean(axis=0))
    err=float(abs(np.asarray(model['coefficients'])-expected).max())
    assert model['converged'] and err<1e-7;r['known']['positive_branch_coefficient_error']=err
    same=fit(feature,np.ones((len(feature),8)))
    assert np.array_equal(np.asarray(same['coefficients']),np.zeros((13,8)))
    parent=a.workspace/'baselines';origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    profile=load(input_path(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    for seed in [None,149921,277139,381611]:
        arrays={}
        for part in ['train','check']:
            source=input_path(origin/(part+'.npz'))
            with np.load(source) as f:audio=f['audio'];z=f['phasors']
            if seed is not None:
                spectrum=np.fft.rfft(audio,axis=0);phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(spectrum));phase[0]=phase[-1]=0
                audio=np.fft.irfft(spectrum*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
                with np.load(input_path(origin/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            feature,power,sos,filtered=observe(audio,z);arrays[part]=(feature,power)
            label=('source' if seed is None else 'phase_'+str(seed))+'_'+part
            path=a.out/(label+'.npz');np.savez_compressed(path,feature=feature,power=power,sos=sos,filtered=filtered)
        if seed is None:
            shape_model,model,effective=compile_model(*arrays['train'],profile)
            save(a.out/'model.json',shape_model);np.savez_compressed(a.out/'effective.npz',responses=effective)
        else:model=fit(*arrays['train'])
        row=dict(seed=seed,model=model,assessment={part:assess_model(model,*v) for part,v in arrays.items()})
        r['fits'].append(row);save(a.out/'report.json',r)
        print(dict(stage='fit',seed=seed,converged=model['converged'],check=row['assessment']['check']['improvement_over_train_constant']),flush=True)
    phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    phase_model=load(input_path(phase_root/'model.json'))
    law=load(input_path(parent/'idle_positive_power_v1/evidence/observe1/report.json'))['observations'][0]['models']['expanded']
    allocation=load(input_path(parent/'idle_post_budget_v1/evidence/observe1/report.json'))['allocation']
    r['phase_model']=phase_model;r['law']=law;r['probability']=allocation['probability']
    for seed in [149921,277139,381611]:
        with np.load(input_path(phase_root/f'motion_{seed}.npz')) as f:values=f['coordinate_nodes']
        buses,traces=render(profile,phase_model,values,law,allocation['probability'],shape_model,seed,24)
        row=dict(seed=seed,seconds=24,files={})
        for name,y in buses.items():
            assert np.isfinite(y).all() and abs(y).max()<1.,(seed,name,'No peak normalization')
            path=a.out/f'{name}_{seed}.wav';sf.write(path,y,48000,subtype='FLOAT')
            row['files'][name]=dict(file=path.name,sha256=sha(path),peak=float(abs(y).max()))
        trace=a.out/f'traces_{seed}.npz';np.savez_compressed(trace,**traces)
        row.update(trace_file=trace.name,trace_sha256=sha(trace))
        before=input_path(phase_root/f'relation_full_{seed}.wav');old,rate=sf.read(before,frames=24*48000,always_2d=True)
        current=sf.read(a.out/row['files']['mix_0.0']['file'],always_2d=True)[0]
        row['old_frozen_mix_comparison']=dict(samples_exact=bool(np.array_equal(current,old)),
            maximum_difference_FS=float(abs(current-old).max()),reference=str(before))
        assert row['old_frozen_mix_comparison']['maximum_difference_FS']<=3e-8
        r['renders'].append(row);save(a.out/'report.json',r)
        print(dict(stage='render',seed=seed,peak=max(v['peak'] for v in row['files'].values()),old=row['old_frozen_mix_comparison']),flush=True)
    r.update(result='finite_phase_conditioned_shape_candidate_pending_audit_and_hearing',
        model_sha256=sha(a.out/'model.json'),seconds_each=24,amounts=[0.,.5,1.],
        source_recorded_timeline_replayed=False,check_used_for_fit=False,runtime_changed=False,
        old6FIR_and13OSC_unchanged=True,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],renders=len(r['renders'])),flush=True)
