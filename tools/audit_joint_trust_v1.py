"""Rebuild saved joint candidates and primal/dual certificates without refitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--coarse',type=Path,required=True)
parser.add_argument('--precise',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
sys.path.insert(0,str(args.workspace/'tools/qp_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from absolute_amplitude_v1.model import AbsoluteModel
from absolute_amplitude_v1.amplitude import cost
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from joint_trust_v1.fit import scales_from_observation


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.joint-trust-audit/1',result='running',sources={},real_audio_read=False,
    real_source_permitted=False,qualification_changed=False,nonlinear_estimator_rerun=False,
    quadratic_solver_rerun=False,cases=[],precise_trace=[])
try:
    source={Path(__file__)}
    parents={name:load(path/'report.json') for name,path in (('coarse',args.coarse),('precise',args.precise))}
    for name,path in (('coarse',args.coarse),('precise',args.precise)):
        value=parents[name]
        assert value['result'] in ('dense_diagnostic_rejected','dense_diagnostic_passed_not_full_qualification')
        report[name+'_report_sha256']=sha(path/'report.json')
        changed=[]
        for relative,digest in value['sources'].items():
            assert sha(path/'exact_sources'/relative)==digest
            if sha(repo/relative)!=digest:
                changed.append(relative)
            source.add(repo/relative)
        if name=='precise':
            assert not changed
        report[name+'_changed_executed_sources']=changed
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
    for name,path in (('coarse',args.coarse),('precise',args.precise)):
        value=parents[name]
        plan=load(path/'effective_plan.json')
        saved=np.load(path/'fit.npz')
        assert np.array_equal(saved['time'],time) and np.array_equal(saved['true_phase_correction'],truth)
        model=AbsoluteModel(time,plan,variant,value['fit']['selected_indices'])
        target=real_rows(model.original.aperture.apply(audio[:,0]))
        parameters=saved['parameters']
        _,phase,envelope=model.original.samples(parameters)
        assert np.array_equal(phase,saved['phase_correction'])
        assessment,_,_=assess(audio,time,truth,phase,parameters,{**plan,'heldout_orders':base['heldout_orders']})
        assert assessment==value['assessment']
        residual=model.original.prediction(parameters)-target
        objective=cost(residual,plan['soft_l1_scale'])
        normalized=float(np.linalg.norm(residual)/np.linalg.norm(target))
        assert objective==value['fit']['final_cost'] and normalized==value['fit']['normalized_projection_residual']
        lower,upper=model.original.bounds(plan,variant)
        error=float(max(0.,np.max(lower-parameters),np.max(parameters-upper)))
        assert error<=1e-9
        accepted=[row for row in value['fit']['history'] if row['accepted']]
        assert len(accepted)==value['fit']['accepted_steps']
        assert all(row['actual_reduction']>0 and row['feasibility']['feasible'] for row in accepted)
        assert all(row['candidate_cost']<row['before_cost'] for row in accepted)
        report['cases'].append(dict(id=name,final_phase_residual_cost_assessment_exact=True,
            assessment=assessment,original_bound_error=error,accepted_steps=len(accepted),
            qp_certified=sum(row['qp']['success'] for row in value['fit']['history']),
            qp_uncertified=sum(not row['qp']['success'] for row in value['fit']['history'])))
    value=parents['precise']
    saved=np.load(args.precise/'fit.npz')
    plan=load(args.precise/'effective_plan.json')
    settings=load(repo/'research/joint_trust_precise_v1_plan.json')
    model=AbsoluteModel(time,plan,variant,value['fit']['selected_indices'])
    target=real_rows(model.original.aperture.apply(audio[:,0]))
    outer,controls=model.unpack(saved['initial_parameters'])
    scales=np.asarray(value['fit']['scales'])
    assert np.array_equal(scales,scales_from_observation(model,outer,controls,target,plan['soft_l1_scale']))
    for row in value['fit']['history']:
        predicted,phase_derivative=model.prediction(outer,controls,True)
        matrix=np.column_stack((phase_derivative,model.design(outer)))*scales[None,:]
        residual=predicted-target
        before=cost(residual,plan['soft_l1_scale'])
        assert before==row['before_cost']
        ratio=residual/plan['soft_l1_scale']
        curvature=(1+ratio**2)**(-1.5)
        gram=matrix.T@(curvature[:,None]*matrix)
        gradient=matrix.T@(residual/np.sqrt(1+ratio**2))
        region=Region(model,outer,controls,scales,row['radius'],settings)
        linear,lower,upper=linear_system(region)
        qp=row['qp']
        x,y=np.asarray(qp['primal_solution']),np.asarray(qp['dual_solution'])
        objective_scale=max(float(abs(gradient).max()),np.finfo(float).tiny)
        assert objective_scale==qp['objective_scale']
        normal=(gram+gram.T)/(2*objective_scale)
        stationarity=float(abs(normal@x+gradient/objective_scale+linear.T@y).max())
        observed=linear@x
        primal=float(max(0.,np.max(lower-observed),np.max(observed-upper)))
        assert stationarity==qp['normalized_dual_stationarity'] and primal==qp['constraint_violation']
        positive=y>1e-12
        negative=y<-1e-12
        complementarity=float(max(0.,np.max(abs(y[positive]*(upper[positive]-observed[positive]))) if positive.any() else 0.,
            np.max(abs(y[negative]*(observed[negative]-lower[negative]))) if negative.any() else 0.))
        certified=bool(qp['status_value']==1 and primal<=1e-9 and stationarity<=1e-8)
        assert certified==qp['success']
        new_outer,new_controls,effective,feasible=region.retract(x)
        assert np.array_equal(new_outer,np.asarray(row['candidate_outer']))
        assert np.array_equal(new_controls,np.asarray(row['candidate_absolute_amplitudes']))
        assert feasible==row['feasibility']
        candidate_cost=cost(model.prediction(new_outer,new_controls)-target,plan['soft_l1_scale'])
        assert candidate_cost==row['candidate_cost']
        predicted_reduction=float(-gradient@effective-.5*effective@gram@effective)
        actual=before-candidate_cost
        assert predicted_reduction==row['predicted_reduction'] and actual==row['actual_reduction']
        accept=bool(feasible['feasible'] and predicted_reduction>0 and actual>0
            and actual/predicted_reduction>=settings['acceptance_ratio'])
        assert accept==row['accepted']
        report['precise_trace'].append(dict(iteration=row['iteration'],primal=primal,stationarity=stationarity,
            complementarity=complementarity,qp_certified=certified,accepted=accept,all_candidate_and_objective_values_exact=True))
        if accept:
            outer,controls=new_outer,new_controls
    assert np.array_equal(model.pack(outer,controls),saved['parameters'])
    old=args.workspace/'references/analysis/absolute_amplitude_v1/final1'
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/path)==digest for path,digest in load(old/filename).items())
    report.update(result='reconstructed_joint_candidates_and_certificates',precise_entire_trace_exact=True,
        C_H=540,voices_and_moving35_unchanged=True,
        limits=['Primal/dual QP certificates do not establish an accurate latent acoustic phase or real-engine timbre',
            'Coarse historical source differences are retained in its exact_sources and not silently rewritten'])
    print(json.dumps(dict(result=report['result'],cases=[{k:r[k] for k in ('id','accepted_steps','qp_certified','qp_uncertified')} for r in report['cases']],trace=len(report['precise_trace']))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
