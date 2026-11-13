"""Qualify radial loss, original constrained-QP adapter and observed initial derivatives."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(args.workspace/'tools/ipm_deps'),str(args.workspace/'tools/qp_deps'),str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows
from complex_radial_v1.checks import controls,rotate
from complex_radial_v1.loss import cost,gradient,hessian_apply


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.complex-radial-controls/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,phase_estimator_qualified=False)
try:
    parent=args.workspace/'references/analysis/correlated_observation_v1/fit1';old=load(parent/'report.json')
    sources={Path(__file__),repo/'research/complex_radial_v1_plan.json',*sorted((repo/'tools/complex_radial_v1').glob('*.py'))}
    for name,digest in old['sources'].items():assert sha(repo/name)==sha(parent/'exact_sources'/name)==digest;sources.add(repo/name)
    for path in sources:
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    plan=load(parent/'effective_plan.json');settings=load(parent/'effective_settings.json');variant=load(repo/'research/minority_phase_v1_plan.json')
    report['controls']=controls(settings)
    inputs=np.load(parent/'input.npz');time,audio,initial=(inputs[k] for k in ('time','audio','initial_parameters'))
    model=QuinticAbsoluteModel(time,plan,variant,[]);model.original.aperture=MarginalAperture(model.original.aperture)
    outer,amplitudes=model.unpack(initial);target=real_rows(model.original.aperture.apply(audio[:,0]))
    value,derivative=model.prediction(outer,amplitudes,True);matrix=np.column_stack((derivative,model.design(outer)))
    rng=np.random.default_rng(128043);direction=rng.normal(size=matrix.shape[1]);direction/=np.linalg.norm(direction)
    step=1e-6;n=len(outer)
    def prediction(multiplier):return model.prediction(outer+multiplier*direction[:n],amplitudes+multiplier*direction[n:].reshape(amplitudes.shape))
    plus,minus=prediction(step),prediction(-step);expected=matrix@direction
    jac_error=float(np.linalg.norm((plus-minus)/(2*step)-expected)/np.linalg.norm(expected))
    residual=value-target;scale=plan['soft_l1_scale'];psi=gradient(residual,scale)
    fd=(cost(plus-target,scale)-cost(minus-target,scale))/(2*step)
    grad_error=abs(fd-float(psi@expected))/max(np.linalg.norm(psi)*np.linalg.norm(expected),1e-30)
    weighted=hessian_apply(residual,matrix,scale,.5);turned_r=rotate(residual,.37);turned_m=rotate(matrix,.37)
    rotated_weighted=hessian_apply(turned_r,turned_m,scale,.5)
    factor_error=float(abs(rotate(weighted,.37)-rotated_weighted).max())
    gradient_error=float(abs(matrix.T@psi-turned_m.T@gradient(turned_r,scale)).max())
    assert jac_error<=plan['rules']['maximum_jacobian_relative_error'] and grad_error<=1e-6
    assert factor_error<=1e-12 and gradient_error<=1e-12
    report.update(result='radial_loss_QP_and_observed_derivative_controls_passed',parent_report_sha256=sha(parent/'report.json'),
        parent_input_sha256=sha(parent/'input.npz'),observed_mixed_jacobian_relative_error=jac_error,
        observed_robust_gradient_relative_error=grad_error,observed_factor_rotation_error=factor_error,
        observed_gradient_rotation_error=gradient_error,truth_or_heldouts_accessed=False,
        limits=['Hessian is the exact radial residual-space Hessian pulled through the linearized model, not the full nonlinear second derivative',
            'These controls do not repair out-of-band leakage or qualify engine phase extraction'])
    print(json.dumps({k:report[k] for k in ('result','observed_mixed_jacobian_relative_error','observed_robust_gradient_relative_error','observed_factor_rotation_error','observed_gradient_rotation_error')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
