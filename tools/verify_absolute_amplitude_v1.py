"""Nonzero active/inactive cone, robust solve and minority-phase controls."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import minimize, Bounds, LinearConstraint
from drive_evidence_v1.sources import sha
from absolute_amplitude_v1.checks import inequalities
from absolute_amplitude_v1.cone import violation
from absolute_amplitude_v1.quadratic import solve
from absolute_amplitude_v1.amplitude import solve_amplitudes, cost
from absolute_amplitude_v1.model import AbsoluteModel


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.absolute-amplitude-independent-controls/1',result='running',sources={},
    real_audio_read=False,real_source_permitted=False,qualification_changed=False,cases=[])
try:
    source={Path(__file__),repo/'research/absolute_amplitude_v1_plan.json',repo/'research/aperture_model_v1_plan.json',
        repo/'research/minority_phase_v1_plan.json'}
    for folder in ('absolute_amplitude_v1','positive_band_envelope_v1','minority_phase_v1','aperture_model_v1'):
        source.update((repo/'tools'/folder).glob('*.py'))
    for path in source:
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    settings=load(repo/'research/absolute_amplitude_v1_plan.json')
    rng=np.random.default_rng(721803)
    for label in ('identity_active','coupled_interior','coupled_active_robust'):
        groups,count=2,4
        initial=np.full((groups,count),.1)
        caps=np.array([.35,.6])
        if label=='identity_active':
            design=np.eye(8)
            target=np.array([.4,.1,.7,.4,.8,1.2,.2,.5])
        else:
            design=rng.normal(0,.3,(45,8))
            controls=np.array([[.2,.19,.22,.18],[.3,.33,.31,.28]])
            target=design@controls.ravel()
            if label.endswith('robust'):
                target+=.04*rng.normal(size=len(target))
                target[0]+=1.5
                caps=np.array([.16,.22])
        upper=np.full(8,np.inf)
        upper[::count]=caps
        constraint=LinearConstraint(inequalities(groups,count,.25),0,np.inf)
        if label.endswith('robust'):
            scale=.08
            result,actual=solve_amplitudes(design,target,initial,.25,caps,scale,settings)
            objective=lambda x:cost(design@x-target,scale)
            def gradient(x):
                residual=design@x-target
                return design.T@(residual/np.sqrt(1+(residual/scale)**2))
        else:
            gram,linear=design.T@design,design.T@target
            result,actual=solve(gram,linear,initial,.25,caps,settings)
            objective=lambda x:.5*np.sum((design@x-target)**2)
            gradient=lambda x:gram@x-linear
        expected=minimize(objective,initial.ravel(),jac=gradient,method='SLSQP',
            constraints=[constraint],bounds=Bounds(np.zeros(8),upper),options=dict(ftol=1e-13,maxiter=300))
        error=float(abs(result.ravel()-expected.x).max())
        actual_cost=objective(result.ravel())
        row=dict(id=label,independent_success=bool(expected.success),actual_success=actual['success'],
            maximum_control_error=error,objective_difference=actual_cost-objective(expected.x),
            minimum_c0=float(result[:,0].min()),constraint_violation=violation(result,.25,caps),
            cap_active=bool(np.any(abs(result[:,0]-caps)<1e-7)),actual=actual)
        report['cases'].append(row)
        assert expected.success and actual['success'] and error<1e-5
        assert row['minimum_c0']>.01 and row['constraint_violation']<1e-10
        assert row['cap_active']==(label!='coupled_interior')
    plan=load(repo/'research/aperture_model_v1_plan.json')
    variant=load(repo/'research/minority_phase_v1_plan.json')
    time=np.arange(plan['cycles']*plan['samples_per_cycle'])/plan['samples_per_cycle']
    model=AbsoluteModel(time,plan,variant,[1])
    m=model.original
    parameters=np.zeros(m.parameter_count)
    parameters[:2*m.parts]=rng.normal(0,.03,2*m.parts)
    first=2*m.parts+m.phase_count
    parameters[2*m.parts:first]=rng.normal(0,.003,m.phase_count)
    parameters[first:m.base_count]=rng.uniform(-.1,.1,m.parts*m.envelope_count)
    parameters[m.base_count:]=rng.normal(0,.02,m.departure_count)
    outer,absolute=model.unpack(parameters)
    prediction,jacobian=model.prediction(outer,absolute,True)
    equivalent=float(abs(prediction-m.prediction(parameters)).max())
    assert equivalent<1e-12
    errors=[]
    for name,index in [('common',m.parts+20),('constant',2),('minority',m.parts+m.phase_count+5)]:
        direction=np.zeros_like(outer)
        direction[index]=1
        step=1e-6
        observed=(model.prediction(outer+step*direction,absolute)-model.prediction(outer-step*direction,absolute))/(2*step)
        error=float(np.linalg.norm(observed-jacobian[:,index])/np.linalg.norm(jacobian[:,index]))
        errors.append(dict(kind=name,relative_error=error))
        assert error<plan['rules']['maximum_jacobian_relative_error']
    report.update(result='passed',minority_model_projection_equivalence=equivalent,derivatives=errors,
        limits=['Independent convex controls do not establish dense-phase or vehicle-timbre qualification'])
    print(json.dumps(dict(result=report['result'],cases=[{k:r[k] for k in ('id','maximum_control_error','minimum_c0','cap_active')} for r in report['cases']],derivatives=errors)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
