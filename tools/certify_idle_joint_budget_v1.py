"""Separating hyperplanes for fixed exact moment budgets, with no new fit."""
import argparse,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha

PAIRS=[(i,j) for i in range(4) for j in range(i,4)]


def certificate(A,row_scale,target,latent):
    eigen,vectors=np.linalg.eigh(latent)
    v=vectors[:,0]
    g=np.array([v[i]*v[j]*(1 if i==j else 2) for i,j in PAIRS])
    u=np.linalg.solve((A/row_scale[:,None]).T,g)
    value=float(u@(target/row_scale))
    residual=float(np.linalg.norm(u@(A/row_scale[:,None])-g))
    assert residual<1e-10 and eigen[0]<0
    assert abs(value-v@latent@v)<1e-8*max(1.,abs(value))
    assert value<0
    return dict(vector=v.tolist(),dual=u.tolist(),dual_residual=residual,
        value=value,Rayleigh=float(v@latent@v),minimum_eigenvalue=float(eigen[0]),
        minimum_required_normalized10_moment_change=float(-value/np.linalg.norm(u)),
        is_lower_bound_not_nearest_model_or_uncertainty=True)


a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_certificate.py')
r=dict(result='running',families={},known=[])
try:
    observed=load(a.input/'report.json')
    assert observed['result']=='both_joint_budget_families_examined_NO_sound_promotion'
    plan=repo/'research/idle_joint_budget_certificate_v1_plan.json'
    shutil.copy2(plan,a.out/'executed_plan.json')
    r['plan_sha256']=sha(plan)
    for case in observed['known']['inverse_controls']:
        if case['name']=='indefinite':
            r['known'].append(dict(family=case['family'],certificate=certificate(np.array(case['A']),
                np.ones(10),np.array(case['target']),np.array(case['solution']['latent']))))
    for family,row in observed['families'].items():
        assert row['solution']['status']=='latent_indefinite_REJECTED'
        z=np.load(a.input/(family+'_budget.npz'))
        result=certificate(z['A'],z['row_scale'],z['target'],np.array(row['solution']['latent']))
        check=np.array(row['check']['check'])
        target=check*np.outer(z['variance'],z['variance'])-z['main']
        packed=np.array([target[i,j] for i,j in PAIRS])/z['row_scale']
        value=float(np.array(result['dual'])@packed)
        result.update(check_value_without_new_fit=value,
            same_training_hyperplane_check_violates=value<0,
            check_lower_bound_with_same_hyperplane=float(max(0.,-value)/np.linalg.norm(result['dual'])))
        r['families'][family]=result
    r.update(result='both_fixed_budget_separation_certificates_computed',
        input_report_sha256=sha(a.input/'report.json'),new_fit_or_audio=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    save(a.out/'report.json',r)
print(r,flush=True)
