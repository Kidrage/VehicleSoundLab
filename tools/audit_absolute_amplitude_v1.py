"""Reconstruct actual alternating output and independently audit its final KKT."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--controls',type=Path,required=True)
parser.add_argument('--direction',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from absolute_amplitude_v1.model import AbsoluteModel
from absolute_amplitude_v1.amplitude import cost
from absolute_amplitude_v1.cone import project,violation
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.absolute-amplitude-audit/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,nonlinear_estimator_rerun=False)
try:
    reports={name:load(path/'report.json') for name,path in (
        ('diagnosis',args.diagnosis),('controls',args.controls),('direction',args.direction))}
    assert reports['diagnosis']['result']=='dense_diagnostic_rejected' and reports['controls']['result']=='passed'
    source={Path(__file__)}
    for name,path in (('diagnosis',args.diagnosis),('controls',args.controls),('direction',args.direction)):
        value=reports[name]
        report[name+'_report_sha256']=sha(path/'report.json')
        for relative,digest in value['sources'].items():
            assert sha(repo/relative)==sha(path/'exact_sources'/relative)==digest
            source.add(repo/relative)
    for path in source:
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    topology=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']=='unknown_thirty_six')
    time,audio,truth,_=make(case,base)
    plan=load(args.diagnosis/'effective_plan.json')
    saved=np.load(args.diagnosis/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    model=AbsoluteModel(time,plan,variant,reports['diagnosis']['fit']['selected_indices'])
    parameters=saved['parameters']
    samples,phase,envelope=model.original.samples(parameters)
    assert np.array_equal(phase,saved['phase_correction'])
    assessment,_,_=assess(audio,time,truth,phase,parameters,{**plan,'heldout_orders':base['heldout_orders']})
    assert assessment==reports['diagnosis']['assessment']
    target=real_rows(model.original.aperture.apply(audio[:,0]))
    residual=model.original.prediction(parameters)-target
    normalized=float(np.linalg.norm(residual)/np.linalg.norm(target))
    assert normalized==reports['diagnosis']['fit']['normalized_projection_residual']
    objective=cost(residual,plan['soft_l1_scale'])
    assert objective==reports['diagnosis']['fit']['final_cost']
    lower,upper=model.original.bounds(plan,variant)
    assert np.max(lower-parameters)<=1e-10 and np.max(parameters-upper)<=1e-10
    outer,absolute=model.unpack(parameters)
    design=model.design(outer)
    ratio=residual/plan['soft_l1_scale']
    weight=1/np.sqrt(1+ratio**2)
    gram=design.T@(weight[:,None]*design)
    largest=float(np.linalg.eigvalsh(gram)[-1])
    gradient=design.T@(weight*residual)
    linear=design.T@(weight*target)
    projected=project((absolute.ravel()-gradient/largest).reshape(absolute.shape),model.bound,model.caps(outer))
    kkt=float(abs(absolute-projected).max()*largest/max(1.,abs(linear).max()))
    original_kkt=reports['diagnosis']['fit']['final_amplitude']['robust_projected_kkt']
    assert abs(kkt-original_kkt)<1e-12 and kkt<=load(repo/'research/absolute_amplitude_v1_plan.json')['irls_gradient_tolerance']
    history=reports['diagnosis']['fit']['history']
    assert len(history)==8 and all(row['amplitude']['success'] for row in history)
    assert all(row['after_cost']<=row['amplitude']['cost']+1e-12<=row['before_cost']+2e-12 for row in history)
    assert all(history[k+1]['before_cost']<=history[k]['after_cost']+1e-12 for k in range(len(history)-1))
    direction=reports['direction']['direction']
    assert not direction['accepted'] and len(direction['trials'])==21 and not any(row['feasible'] for row in direction['trials'])
    direction_saved=np.load(args.direction/'step.npz')
    assert np.array_equal(direction_saved['phase_correction'],phase)
    assert direction['independent_sample_differential_relative_error']<plan['rules']['maximum_jacobian_relative_error']
    assert direction['ordinary_joint_finite_difference_relative_error']>plan['rules']['maximum_jacobian_relative_error']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        original=load(args.workspace/'references/analysis/guard_observation_v1/final1'/filename)
        assert all(sha(repo/relative)==digest for relative,digest in original.items())
    report.update(result='reconstructed_actual_output_no_qualification',assessment=assessment,
        phase_residual_cost_assessment_exact=True,original_bounds_retained=True,
        independent_final_amplitude_kkt=kkt,original_final_amplitude_kkt=original_kkt,
        amplitude_constraint_violation=violation(absolute,model.bound,model.caps(outer)),
        objective_reduction_factor=reports['diagnosis']['fit']['initial_cost']/objective,
        all_eight_block_objectives_monotone=True,ordinary_joint_differential_failed_preserved=True,
        independent_joint_sample_differential_passed=True,joint_direction_not_adopted=True,
        C_H=540,voices_and_moving35_unchanged=True)
    print(json.dumps({key:report[key] for key in ('result','phase_residual_cost_assessment_exact','independent_final_amplitude_kkt','objective_reduction_factor')}),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
