"""Actual POST full marginal/cross latent feasibility, retaining invalid solutions."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import stats
from research_archive_v1 import load,save,sha
from idle_post_budget_v1.response import kernels,support
from idle_post_budget_v1.budget import summarize
from idle_joint_budget_v1.budget import solve,pack
from idle_post_joint_v1.operator import joint_operator,family_matrix,PAIRS
from idle_post_joint_v1.checks import run

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},parent_manifests={},families={})
try:
    plan_path=repo/'research/idle_post_joint_v1_plan.json';plan=load(plan_path)
    sources=[Path(__file__),plan_path,repo/'tools/research_archive_v1.py',repo/'tools/idle_wave_budget_v1/moments.py',
        repo/'tools/idle_joint_cumulant_v1/moments.py',repo/'tools/idle_joint_budget_v1/budget.py',repo/'tools/idle_joint_budget_v1/checks.py',
        repo/'tools/idle_post_budget_v1/response.py',repo/'tools/idle_post_budget_v1/budget.py',
        *sorted((repo/'tools/idle_post_joint_v1').glob('*.py'))]
    for path in sources:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    r['known']=run(a.out/'known');print(dict(stage='known',tensor_error=r['known']['nonstationary_tensor_error']),flush=True)
    tables={}
    for name in plan['parents']:
        root=a.workspace/'baselines'/name;r['parent_manifests'][name]=sha(root/'manifest.json')
        tables[name]={row['path']:row['sha256'] for row in load(root/'manifest.json')['files']}
    def parent(name,file):
        path=a.workspace/'baselines'/name/file;assert sha(path)==tables[name][file]
        r['inputs'][str(path)]=sha(path);return path
    previous=load(parent('idle_post_budget_v1','evidence/observe1/report.json'))
    assert previous['result']=='all_POST_zero_budgets_and_TRAIN_allocation_complete_NO_promotion'
    with np.load(parent('idle_post_budget_v1','evidence/observe1/conditional_fields.npz')) as archive:fields={k:archive[k] for k in archive.files}
    profile=load(parent('fixed_source_profiles_v1','evidence/trial1/F2_tailpipe/profile.json'))
    with np.load(parent('idle_wave_budget_v1','evidence/observe2/architecture.npz')) as archive:
        v,sos,warmup=archive['variance'],archive['sos'],int(archive['warmup'])
    observers=[support(s)[0] for s in sos];origins=fields['origins'].reshape(-1)
    taps=[np.asarray(k['taps'])*k['gain'] for k in profile['kernels'][2:]]
    operator=np.empty((len(origins),10,10));error=np.empty_like(operator)
    epsilon=fields['epsilon'][2:].T
    for first in range(0,len(origins),32):
        last=min(first+32,len(origins))
        K=np.stack([kernels(warmup+origins[first:last],np.sqrt(v[:,i+2]),tap,observers) for i,tap in enumerate(taps)],axis=2)
        operator[first:last],error[first:last]=joint_operator(K,epsilon)
        if first%256==224:print(dict(stage='all_POST_origins',completed=last,total=len(origins)),flush=True)
    operator=operator.reshape(2,1024,10,10);error=error.reshape(operator.shape)
    diagonal=np.array([[fields['operator'][block,:,b,c,:] for b,c in PAIRS] for block in range(2)]).transpose(0,2,1,3)
    difference=float(abs(operator[:,:,:,[0,4,7,9]]-diagonal).max());assert difference<1e-20
    states=[summarize(fields['main'][b],fields['covariance'][b],fields['operator'][b]) for b in range(2)]
    r['previous_diagonal_error']=difference;r['operator_bound_max']=error.max(axis=(0,1)).tolist()
    # TRAIN solutions persisted before the check predictions are evaluated.
    for family,multiplier in [('variance_factors',3),('compound_sign_groups',1)]:
        matrix=family_matrix(operator.mean(axis=1),multiplier)
        target=fields['sourceQ'][0]*states[0]['denominator']-states[0]['gaussian']
        solution=solve(matrix[0],target,states[0]['denominator'],family)
        save(a.out/(family+'_train.json'),solution)
        row=dict(multiplier=multiplier,solution=solution,train_solution_sha256=sha(a.out/(family+'_train.json')))
        if 'latent' in solution:
            latent=pack(np.asarray(solution['latent']))
            row['algebraic_predictions_NOT_automatically_generative']=[((matrix[b]@latent+states[b]['gaussian'])/states[b]['denominator']).tolist() for b in range(2)]
        leave=[]
        for group in range(64):
            keep=np.arange(1024)//16!=group
            selected=[summarize(fields['main'][b,keep],fields['covariance'][b,keep],fields['operator'][b,keep]) for b in range(2)]
            A=family_matrix(operator[:,keep].mean(axis=1),multiplier)
            debt=fields['sourceQ'][0]*selected[0]['denominator']-selected[0]['gaussian']
            fit=solve(A[0],debt,selected[0]['denominator'],family)
            record=dict(group=group,status=fit['status'],eigenvalues=fit.get('eigenvalues'),minimum_entry=fit.get('minimum_entry'))
            if 'latent' in fit:
                coefficients=pack(np.asarray(fit['latent']));record['latent']=fit['latent']
                record['predictions']=[((A[b]@coefficients+selected[b]['gaussian'])/selected[b]['denominator']).tolist() for b in range(2)]
            leave.append(record)
        row['leave_groups']=leave
        if all(z['eigenvalues'] is not None for z in leave):
            minimum=np.array([z['eigenvalues'][0] for z in leave]);point=solution['eigenvalues'][0]
            se=np.sqrt(63/64*np.sum((minimum-minimum.mean())**2));radius=stats.t.ppf(.975,63)*se
            row['minimum_eigenvalue_time_MC']=dict(point=point,se=float(se),approx_point95=[point-radius,point+radius],
                leave_range=[float(minimum.min()),float(minimum.max())],plugin_bias=float(63*(minimum.mean()-point)))
        r['families'][family]=row
        print(dict(family=family,status=solution['status'],eigen=solution.get('eigenvalues')),flush=True)
    path=a.out/'joint_operators.npz';np.savez_compressed(path,operator=operator,error=error,origins=fields['origins'])
    r.update(result='both_actual_POST_joint_families_examined_NO_promotion',data_file=path.name,data_sha256=sha(path),plan=plan,
        all2048_origins_retained=True,sourceQ=fields['sourceQ'].tolist(),previous_independent_predictions=previous['new_predictions'],
        finite_time_MC_NOT_source_impossibility=True,full_lag_qualified=False,audio_or_runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
