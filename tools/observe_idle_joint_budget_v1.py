"""TRAIN-only full-budget feasibility; invalid solutions remain explicitly invalid."""
import argparse,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_joint_budget_v1.budget import operator,pack,unpack,solve
from idle_joint_budget_v1.checks import run

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},families={})
try:
    plan_path=repo/'research/idle_joint_budget_v1_plan.json'
    plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',
                 repo/'tools/idle_joint_cumulant_v1/moments.py',
                 *sorted((repo/'tools/idle_joint_budget_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    known=a.out/'known';known.mkdir()
    r['known']=run(known)
    save(a.out/'known_report.json',r['known'])
    print(dict(stage='known_controls_passed',Gaussian_FIR_error=r['known']['Gaussian_FIR']['error'],
        Poisson_error=r['known']['Poisson_binomial']['error'],inverse_controls=6),flush=True)
    parent=a.workspace/'baselines/idle_joint_cumulant_v1'
    manifest=load(parent/'manifest.json');table={v['path']:v['sha256'] for v in manifest['files']}
    r['parent_manifest_sha256']=sha(parent/'manifest.json')
    def read(name):
        path=parent/name
        assert sha(path)==table[name]
        r['inputs'][name]=table[name]
        return path
    validation=load(read('validation.json'))
    assert validation['audit']['observations']==57 and validation['audit']['matrices']==114
    observed=load(read('evidence/observe1/report.json'))
    arrays=np.load(read('evidence/observe1/architecture.npz'))
    h=arrays['responses'][:,2:6,:]
    variance=arrays['variance'];outer=np.outer(variance,variance)
    main=arrays['main_cumulant']
    train=np.array(next(v for v in observed['observations'] if v['label']=='training')['raw']['normalized'])
    target=train*outer-main
    row_scale=pack(outer)
    for family,multiplier in [('variance_factors',3),('compound_sign_groups',1)]:
        A=operator(h,multiplier)
        solution=solve(A,pack(target),row_scale,family)
        save(a.out/(family+'_train.json'),solution)
        np.savez_compressed(a.out/(family+'_budget.npz'),A=A,target=pack(target),row_scale=row_scale,
            h=h,variance=variance,main=main)
        r['families'][family]=dict(multiplier=multiplier,solution=solution,
            train_solution_sha256=sha(a.out/(family+'_train.json')))
        print(dict(family=family,status=solution['status'],eigenvalues=solution.get('eigenvalues'),
            upper_bound=solution.get('existence_upper_bound')),flush=True)
    # Check observations were already inspected in the parent, but are never used in this solve.
    check=np.array(next(v for v in observed['observations'] if v['label']=='check')['raw']['normalized'])
    old=np.array(observed['theoretical_raw']['1'])
    for family,row in r['families'].items():
        solution=row['solution']
        if 'prediction' not in solution:
            row['check']=dict(status='no_prediction_rank_unknown')
            continue
        prediction=(unpack(solution['prediction'])+main)/outer
        row['check']=dict(prediction=prediction.tolist(),train=train.tolist(),check=check.tolist(),
            old_independent=old.tolist(),new_error=(prediction-check).tolist(),old_error=(old-check).tolist(),
            error_norm=float(np.linalg.norm(prediction-check)),old_error_norm=float(np.linalg.norm(old-check)),
            generative_certificate=solution['status']=='nonnegative_factor_CERTIFIED',
            rate_selected=False,previously_inspected_same_recording=True)
    r.update(result='both_joint_budget_families_examined_NO_sound_promotion',plan=plan,
        training_only=True,new_audio_or_profile=False,runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    save(a.out/'report.json',r)
