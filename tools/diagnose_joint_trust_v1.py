"""One observed joint trust-region candidate, original dense positive and gates."""
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
parser.add_argument('--plan',type=Path,default=Path('research/joint_trust_v1_plan.json'))
parser.add_argument('--backend',choices=['admm','osqp'],default='admm')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
if args.backend=='osqp':
    sys.path.insert(0,str(args.workspace/'tools/qp_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from aperture_model_v1.checks import assess
from joint_trust_v1.checks import controls
from joint_trust_v1.fit import estimate


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.joint-trust-diagnosis/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,runtime_changed=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='dense_diagnostic_rejected'
    report['parent_report_sha256']=sha(args.parent/'report.json')
    settings_path=repo/args.plan
    settings=load(settings_path)
    topology=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    from joint_trust_v1.quadratic import solve as qp_solver
    if args.backend=='osqp':
        from joint_trust_v1.osqp_backend import solve as qp_solver
    sources={Path(__file__),settings_path}|set((repo/'tools/joint_trust_v1').glob('*.py'))|{repo/name for name in parent['sources']}
    sources.add(repo/'tools/offline_qp_requirements.txt')
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.parent/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    report['backend']=args.backend
    import scipy
    report['numeric_libraries']=dict(numpy=np.__version__,scipy=scipy.__version__)
    if args.backend=='osqp':
        shutil.copy2(args.workspace/'tools/qp_install_report.json',args.out/'qp_install_report.json')
        report['qp_install_report_sha256']=sha(args.out/'qp_install_report.json')
    report['controls']=controls(base,variant,settings,qp_solver)
    save(args.out/'controls.json',report['controls'])
    print(json.dumps(dict(status='joint_controls_passed',controls=report['controls'])),flush=True)
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    plan=load(args.parent/'effective_plan.json')
    save(args.out/'effective_plan.json',plan)
    saved=np.load(args.parent/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    selected=parent['fit']['selected_indices']
    started=timer.perf_counter()
    def progress(row):
        save(args.out/'progress.json',row)
        print(json.dumps(dict(iteration=row['iteration'],radius=row['radius'],accepted=row['accepted'],
            cost=row['candidate_cost'],ratio=row['ratio'],qp_success=row['qp']['success'],
            qp_iterations=row['qp']['iterations'],qp_reason=row['qp'].get('reason'),
            qp_kkt=row['qp'].get('projected_kkt'),projection_iterations=row['qp']['maximum_projection_iterations'])),flush=True)
    parameters,phase,report['fit']=estimate(audio,time,plan,variant,settings,selected,saved['parameters'],progress,qp_solver)
    report['fit']['seconds']=timer.perf_counter()-started
    np.savez_compressed(args.out/'fit.npz',time=time,parameters=parameters,initial_parameters=saved['parameters'],
        phase_correction=phase,true_phase_correction=truth)
    if report['fit']['observation_supported']:
        report['assessment'],positions,oracle_positions=assess(audio,time,truth,phase,parameters,
            {**plan,'heldout_orders':base['heldout_orders']})
        np.savez_compressed(args.out/'coordinates.npz',positions=positions,oracle_positions=oracle_positions)
    report['original_assessment']=parent['assessment']
    report['result']='dense_diagnostic_passed_not_full_qualification' if report.get('assessment',{}).get('qualified') else 'dense_diagnostic_rejected'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    interior=(time>=5)&(time<35)
    for correction,label in ((saved['phase_correction'],'Alternating blocks'),(phase,'Joint constrained trust region')):
        error=correction-truth
        error-=np.median(error[interior])
        axes[0].plot(time[interior],error[interior],label=label)
    for sign in (-1,1):
        axes[0].axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)')
    axes[0].legend(fontsize=8)
    history=report['fit']['history']
    accepted=[r for r in history if r['accepted']]
    if accepted:
        axes[1].semilogy([r['iteration'] for r in accepted],[r['candidate_cost'] for r in accepted],marker='o')
    axes[1].set(xlabel='Trust-region iteration',ylabel='Accepted original robust objective')
    fig.tight_layout(); fig.savefig(args.out/'joint_trust.png',dpi=150); plt.close(fig)
    report['plot_sha256']=sha(args.out/'joint_trust.png')
    print(json.dumps(dict(result=report['result'],accepted_steps=report['fit']['accepted_steps'],
        final_cost=report['fit']['final_cost'],assessment=report.get('assessment'),seconds=report['fit']['seconds'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
