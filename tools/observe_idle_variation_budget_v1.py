"""Observe actual frozen idle buses before fitting further stochastic parameters."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_variation_budget_v1.observe import observe
from idle_variation_budget_v1.variation import summarize,budget,known,BANDS,LAGS
from idle_conditioned_detail_v1.features import phases
from idle_phase_recipe_v1.phase import spline,phasors

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},cases=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def record(label,coefficients,reference,metadata,conditions=None):
    selected=coefficients[:,:,[1,2,4]];result=summarize(selected[:,0],reference)
    arrays=dict(coefficients=coefficients,reference=reference,**result)
    stats={key:result[key].tolist() for key in ['std','rho_100_200_500ms','log_std','temporal_power','normalized_mean']}
    if coefficients.shape[1]==3:
        b=budget(selected,reference);arrays.update(b)
        identity=float(abs(coefficients[:,0]-coefficients[:,1]-coefficients[:,2]).max());assert identity<1e-10
        stats.update(budget_identity_error=b['budget_identity_error'],coefficient_sum_error=identity,
            main_std=b['main_std'].tolist(),detail_std=b['detail_std'].tolist(),lag0_signed_variance_ratios=b['lag0_signed_variance_ratios'].tolist())
    if conditions is not None:arrays['design_condition']=conditions
    path=a.out/(label+'.npz');np.savez_compressed(path,**arrays)
    r['cases'].append(dict(label=label,metadata=metadata,file=path.name,sha256=sha(path),stats=stats))
    save(a.out/'report.json',r)


try:
    names=['tools/observe_idle_variation_budget_v1.py','tools/idle_variation_budget_v1/observe.py',
        'tools/idle_variation_budget_v1/variation.py','tools/idle_conditioned_detail_v1/features.py',
        'tools/idle_phase_recipe_v1/phase.py','tools/research_archive_v1.py','research/idle_variation_budget_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known_budget.npz',**arrays)
    # New multi-bus observer is checked against previously qualified known inputs.
    root=a.workspace/'baselines/joint_osc_forward_v1/evidence/run2';spec=load(track(root/'spec.json'))
    with np.load(track(root/'joint_AM_149921.npz')) as f:mix=f['audio'][:144000];target=f['train_true_coefficients']
    with np.load(track(root/'phase_only_149921.npz')) as f:main=f['audio'][:144000]
    with np.load(track(root/'stream_149921.npz')) as f:z=f['phasors'][:144000]
    buses=np.column_stack((mix,main,mix-main));c,cond=observe(buses,spec['frequencies'],z)
    e=float(abs(c[:,0]-target).max());assert e<1e-10;r['known']['multi_bus_previous_coefficients_error']=e
    record('known_forward',c,np.asarray(spec['amplitude'])[[1,2,4]],dict(kind='known',phase_basis='procedural'),cond)
    parent=a.workspace/'baselines/idle_local_partition_v1/evidence';source=parent/'observe1';pr=load(track(source/'report.json'))
    references={}
    for row in pr['cases']:
        if row['metadata']['kind'] not in ['source','samePSD_control'] or row['metadata']['part']!='train':continue
        with np.load(track(source/row['file'])) as f:b=f['global_coefficients'][:,0]
        references[row['label'].removesuffix('_train')]=(b[:13]-1j*b[13:26])[[1,2,4]]
    for row in pr['cases']:
        if row['metadata']['kind'] not in ['source','samePSD_control']:continue
        file=track(source/row['file']);assert sha(file)==row['sha256']
        with np.load(file) as f:c=f['local_coefficients'][:,None,:]
        family=row['label'].rsplit('_',1)[0]
        record(row['label'],c,references[family],dict(**row['metadata'],phase_basis='measured_acoustic',input_file=str(file)))
    profile=load(track(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    freq=np.array(profile['modal']['frequencies_hz'])
    new_model=load(track(parent/'compile2/model.json'))
    phase_root=a.workspace/'baselines/idle_phase_recipe_v1/evidence/render2';phase_model=load(track(phase_root/'model.json'))
    renders=load(track(parent/'render1/report.json'));assert renders['result']=='finite_idle_joint_budget_pending_audit'
    old_reference=np.array(profile['modal']['amplitude_LR'])[[1,2,4],0];new_reference=np.array(new_model['main_amplitude_LR'])[:,0]
    for row in renders['renders']:
        seed=row['seed'];motion_path=track(phase_root/f'motion_{seed}.npz')
        with np.load(motion_path) as f:motion=spline(phase_model,f['coordinate_nodes'])
        for condition in ['0.0','0.5','1.0']:
            paths={key:track(parent/'render1'/row['files'][key+'_'+condition]['file']) for key in ['mix','main']}
            waves={}
            for key,path in paths.items():
                assert sha(path)==row['files'][key+'_'+condition]['sha256'];audio,rate=sf.read(path,always_2d=True)
                assert rate==48000 and len(audio)==1152000;waves[key]=audio[:,0]
            for block,first in enumerate(range(0,1152000,144000)):
                mix=waves['mix'][first:first+144000];main=waves['main'][first:first+144000]
                buses=np.column_stack((mix,main,mix-main))
                z0=phasors(phase_model,motion,np.arange(first,first+144000)/48000)
                z1=phases(mix,freq[[1,2,4]])
                for basis,z in [('procedural',z0),('measured_acoustic',z1)]:
                    c,cond=observe(buses,freq,z)
                    record(f'generated_{seed}_{condition}_{block}_{basis}',c,
                        old_reference if condition=='0.0' else new_reference,
                        dict(kind='generated',seed=seed,condition=condition,block=block,first_frame=first,
                            phase_basis=basis,mix_file=str(paths['mix']),main_file=str(paths['main']),motion_file=str(motion_path)),cond)
            print(dict(seed=seed,condition=condition,observed_blocks=8,phase_bases=2),flush=True)
    assert len(r['cases'])==153
    r.update(result='actual_idle_bus_variation_observed_pending_audit',source_control_cases=8,generated_cases=144,
        lag_seconds=(LAGS*.02).tolist(),temporal_bands_hz=BANDS.tolist(),reference_CHECK_refitted=False,
        phase_truth_known_only_for_procedural_audio=True,source_physical_decomposition=False,
        new_audio_or_model=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],cases=len(r['cases'])),flush=True)
