"""Actual observation-only same-spacing quintic phase diagnostic."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--parent',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
sys.path.insert(0,str(args.workspace/'tools/qp_deps'))
import numpy as np
import scipy
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from aperture_model_v1.checks import assess
from joint_trust_v1.fit import estimate_with_model
from joint_trust_v1.osqp_backend import solve
from quintic_phase_v1.model import QuinticAbsoluteModel
from quintic_phase_v1.initialize import migrate
from quintic_phase_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.quintic-phase-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.parent/'report.json')
    settings_path=repo/'research/quintic_phase_v1_plan.json'
    settings=load(settings_path)
    trust_path=repo/settings['parent_plan']
    trust=load(trust_path)
    topology=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    source={Path(__file__),settings_path,trust_path,repo/'tools/offline_qp_requirements.txt'}|{repo/name for name in parent['sources']}
    for folder in ('quintic_phase_v1','joint_trust_v1'):
        source.update((repo/'tools'/folder).glob('*.py'))
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.parent/'exact_sources'/name)==digest
    for path in source:
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    prior=args.workspace/'references/analysis/joint_trust_v1/dense2'
    prior_report=load(prior/'report.json')
    for name in ('constraints.py','quadratic.py','osqp_backend.py','checks.py'):
        relative='tools/joint_trust_v1/'+name
        assert sha(repo/relative)==sha(prior/'exact_sources'/relative)==prior_report['sources'][relative]
    report['reused_independent_QP_controls']=dict(report_sha256=sha(prior/'report.json'),
        controls_sha256=sha(prior/'controls.json'), unchanged_solver_constraint_sources=True,
        numeric_libraries=dict(numpy=np.__version__,scipy=scipy.__version__))
    assert prior_report['controls']['passed']
    assert prior_report['numeric_libraries']==report['reused_independent_QP_controls']['numeric_libraries']
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    plan=load(args.parent/'effective_plan.json')
    save(args.out/'effective_plan.json',plan)
    saved=np.load(args.parent/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    selected=parent['fit']['selected_indices']
    assert selected==[]
    report['controls']=controls(time,plan,variant,saved['parameters'])
    initial,report['initialization']=migrate(time,plan,variant,selected,saved['parameters'])
    save(args.out/'controls.json',report['controls'])
    save(args.out/'initialization.json',report['initialization'])
    print(json.dumps(dict(status='quintic_controls_passed',initialization=report['initialization'],
        jacobian=report['controls']['jacobian'])),flush=True)
    started=timer.perf_counter()
    model=QuinticAbsoluteModel(time,plan,variant,selected)
    def progress(row):
        save(args.out/'progress.json',row)
        print(json.dumps(dict(iteration=row['iteration'],radius=row['radius'],accepted=row['accepted'],
            cost=row['candidate_cost'],ratio=row['ratio'],qp_success=row['qp']['success'],
            qp_iterations=row['qp']['iterations'],stationarity=row['qp']['normalized_dual_stationarity'])),flush=True)
    parameters,phase,report['fit']=estimate_with_model(model,audio,time,plan,variant,trust,initial,progress,solve)
    report['fit']['seconds']=timer.perf_counter()-started
    np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=initial,
        previous_parameters=saved['parameters'],phase_correction=phase,true_phase_correction=truth)
    if report['fit']['observation_supported']:
        report['assessment'],positions,oracle_positions=assess(audio,time,truth,phase,parameters,
            {**plan,'heldout_orders':base['heldout_orders']})
        np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    report['result']='dense_diagnostic_passed_not_full_qualification' if report.get('assessment',{}).get('qualified') else 'dense_diagnostic_rejected'
    report['original_assessment']=parent['assessment']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    interior=(time>=5)&(time<35)
    initial_phase=model.original.samples(initial)[1]
    for correction,label in ((saved['phase_correction'],'Original observed cubic'),(initial_phase,'Bounded observed migration'),(phase,'Actual quintic estimate')):
        error=correction-truth;error-=np.median(error[interior])
        axes[0].plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axes[0].axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)');axes[0].legend(fontsize=7)
    accepted=[row for row in report['fit']['history'] if row['accepted']]
    if accepted:
        axes[1].semilogy([r['iteration'] for r in accepted],[r['candidate_cost'] for r in accepted],marker='o')
    axes[1].set(xlabel='Trust-region iteration',ylabel='Accepted original robust objective')
    fig.tight_layout();fig.savefig(args.out/'quintic_phase.png',dpi=150);plt.close(fig)
    report['plot_sha256']=sha(args.out/'quintic_phase.png')
    print(json.dumps(dict(result=report['result'],accepted=report['fit']['accepted_steps'],
        final_cost=report['fit']['final_cost'],assessment=report.get('assessment'),seconds=report['fit']['seconds'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
