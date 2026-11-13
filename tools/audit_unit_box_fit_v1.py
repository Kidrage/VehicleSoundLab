"""Replay every unit-box mapped QP and original nonlinear decision, no solves."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'), str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from complex_radial_v1.loss import cost, hessian_apply
from complex_radial_v1.audit import explicit, relative
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from phase_envelope_blocks_v1.checks import certificate_function
from radial_majorizer_v1.audit import scalar_cost, independent_wave_and_jacobian
from joint_radial_majorizer_v1.audit import geometry
from unit_box_qp_v1.audit import check as check_unit


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sorted_scale(residual, floor):
    n = len(residual)//2; a = sorted(np.sqrt(residual[:n]**2+residual[n:]**2).tolist()); k = len(a)//2
    median = a[k] if len(a)%2 else .5*(a[k-1]+a[k])
    return max(floor, median), median


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.unit-box-qp-audit/1', result='running', sources={}, trace=[],
    real_audio_read=False, model_exported=False, runtime_changed=False, nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    candidate=args.workspace/'references/analysis/unit_box_qp_v1/fit1'
    observed=load(candidate/'report.json'); fitted=load(candidate/'fit.json')
    assert observed['result'] == 'known_unit_box_rejected' and observed['fit_report_sha256'] == sha(candidate/'fit.json')
    sources={Path(__file__),repo/'tools/radial_majorizer_v1/audit.py',repo/'tools/complex_radial_v1/audit.py',
        repo/'tools/joint_radial_majorizer_v1/audit.py',repo/'research/joint_radial_majorizer_v1_audit_review.json',repo/'tools/unit_box_qp_v1/audit.py'}
    for name,digest in observed['sources'].items():
        assert sha(repo/name) == sha(candidate/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel=path.relative_to(repo); dest=args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest); r['sources'][rel.as_posix()]=sha(path)
    r['candidate_report_sha256']=sha(candidate/'report.json')
    certificate=certificate_function(repo/'tools/audit_interior_qp_v1.py')
    parent=args.workspace/'references/analysis/joint_radial_majorizer_v1/fit1'
    assert observed['parent_report_sha256'] == sha(parent/'report.json') and observed['parent_fit_sha256'] == sha(parent/'fit.json')
    previous=load(parent/'fit.json'); inputs=np.load(candidate/'input.npz'); original=np.load(parent/'input.npz')
    assert all(np.array_equal(inputs[k],original[k]) for k in inputs.files)
    time,audio,initial=(inputs[k] for k in ('time','audio','initial_parameters'))
    plan,settings=load(candidate/'effective_plan.json'),load(candidate/'effective_settings.json')
    assert plan == load(parent/'effective_plan.json') and settings == load(parent/'effective_settings.json')
    variant=load(repo/'research/minority_phase_v1_plan.json')
    model=QuinticAbsoluteModel(time,plan,variant,[]); model.original.aperture=OrthogonalBand(len(time),plan)
    target=real_rows(model.original.aperture.apply(audio[:,0])); floor=plan['soft_l1_scale']
    scales=np.asarray(fitted['scales']); assert np.array_equal(scales,np.asarray(previous['scales']))
    outer,controls=model.unpack(initial); residual=model.prediction(outer,controls)-target
    stage,median=sorted_scale(residual,floor); assert abs(stage-fitted['initial_stage_scale']) < 1e-12
    value,jacobian=model.prediction(outer,controls,True); unscaled=np.column_stack((jacobian,model.design(outer)))
    factor=hessian_apply(value-target,unscaled,fitted['initial_stage_scale'],.5)
    independent_factor=explicit(value-target,unscaled,fitted['initial_stage_scale'])[2]
    assert relative(factor,independent_factor) <= 1e-12
    norms=np.linalg.norm(factor,axis=0)
    theta=np.minimum(1/np.maximum(norms[:len(outer)],1e-30),np.r_[np.full(model.parts,np.pi),np.full(model.original.phase_count,model.phase_bound)])
    group=np.minimum(1/np.maximum(norms[len(outer):].reshape(controls.shape).max(axis=1),1e-30),np.sqrt(2.))
    assert np.array_equal(scales,np.r_[theta,np.broadcast_to(group[:,None],controls.shape).ravel()])
    radius=settings['initial_radius']; max_geometry=max_wave=max_loss=0.
    for index,row in enumerate(fitted['history'],1):
        assert row['iteration'] == index and row['radius'] == radius
        value,jacobian=model.prediction(outer,controls,True)
        matrix=np.column_stack((jacobian,model.design(outer)))*scales[None,:]
        residual=value-target; stage=row['stage_scale']; expected_stage,expected_median=sorted_scale(residual,floor)
        assert abs(stage-expected_stage) < 1e-12 and abs(row['observed_residual_median']-expected_median) < 1e-12
        gram,g,weighted,errors,v,roundoff=geometry(residual,matrix,stage); max_geometry=max(max_geometry,max(errors.values()))
        region=Region(model,outer,controls,scales,radius,settings); system=linear_system(region)
        checked=check_unit(row['qp'],gram,g,weighted,*system,certificate)
        new_outer,new_controls,effective,feasible=region.retract(np.asarray(row['qp']['primal_solution']))
        assert feasible == row['feasibility'] and np.array_equal(new_outer,row['candidate_outer'])
        assert np.array_equal(new_controls,row['candidate_absolute_amplitudes'])
        production=model.prediction(new_outer,new_controls)
        independent=independent_wave_and_jacobian(model,new_outer,new_controls)[0]
        wave_error=float(abs(production-independent).max()); max_wave=max(max_wave,wave_error); assert wave_error < 1e-12
        before,original_before=cost(residual,stage),cost(residual,floor)
        candidate_cost,original_candidate=cost(production-target,stage),cost(production-target,floor)
        loss_error=max(abs(scalar_cost(independent-target,stage)-candidate_cost),abs(scalar_cost(independent-target,floor)-original_candidate))
        max_loss=max(max_loss,loss_error); assert loss_error < 1e-12
        predicted=float(-g@effective-.5*effective@gram@effective)
        actual,original_actual=before-candidate_cost,original_before-original_candidate
        ratio=actual/predicted if predicted > 0 else None
        accepted=bool(checked['success'] and feasible['feasible'] and predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'] and original_actual > 0)
        for key,expected in dict(before_cost=before,candidate_cost=candidate_cost,original_before_cost=original_before,
            original_candidate_cost=original_candidate,predicted_reduction=predicted,actual_reduction=actual,
            original_actual_reduction=original_actual,ratio=ratio,accepted=accepted).items(): assert row[key] == expected
        lin=residual+matrix@effective; n=len(residual)//2
        major=float(before+.5*np.sum(v*((lin[:n]**2+lin[n:]**2)-(residual[:n]**2+residual[n:]**2))))
        bound_margin=major-scalar_cost(lin,stage); assert bound_margin >= -1e-12
        assert abs(major-(before-predicted)) < 1e-12
        if accepted: outer,controls=new_outer,new_controls
        if not accepted or ratio < .25: radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius: radius=min(2*radius,settings['maximum_radius'])
        r['trace'].append(dict(iteration=index,accepted=accepted,certificate=checked,feasibility=feasible,
            geometry_errors=errors,factor_gradient_roundoff=roundoff,linear_residual_majorizer_margin=bound_margin,
            objectives_decisions_radius_exact=True,legacy_adapter_factor_source_not_curvature_evidence=True))
        if radius < settings['minimum_radius']: assert index == len(fitted['history'])
    parameters=model.pack(outer,controls); saved=np.load(candidate/'fit.npz')
    assert np.array_equal(parameters,saved['parameters']) and radius == fitted['final_radius']
    _,phase,envelope=model.original.samples(parameters); assert np.array_equal(phase,saved['phase_correction'])
    residual=model.original.prediction(parameters)-target
    assert cost(residual,floor) == fitted['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == fitted['normalized_projection_residual']
    stage,median=sorted_scale(residual,floor); assert abs(stage-fitted['final_stage_scale']) < 1e-12
    truth=.045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2); truth -= truth[0]
    inside=(time >= 5)&(time < 35); error=phase-truth; error -= np.median(error[inside])
    p95=float(np.percentile(abs(error[inside]),95)); root_error=float(np.percentile(abs(np.gradient(phase,time)-np.gradient(truth,time))[inside]/(1+np.gradient(truth,time))[inside],95))
    assert p95 == observed['assessment']['phase_p95_cycles'] and root_error == observed['assessment']['root_relative_p95']
    assessed=np.load(candidate/'assessment.npz'); assert np.array_equal(truth,assessed['true_phase']) and np.array_equal(error,assessed['phase_error'])
    failed=[x['iteration'] for x in r['trace'] if not x['certificate']['success']]
    r.update(result='all20_unit_box_steps_including3_QP_failures_independently_rebuilt',
        actual_QPs=len(r['trace']),QPs_certified=len(r['trace'])-len(failed),QP_failure_steps=failed,
        accepted_steps=sum(x['accepted'] for x in r['trace']),geometry_maximum_relative_error=max_geometry,
        original_factor_relative_gate_failed_steps=[x['iteration'] for x in r['trace'] if not x['factor_gradient_roundoff']['original_gate1e12_passed']],
        original_factor_relative_gates_all_passed=all(x['factor_gradient_roundoff']['original_gate1e12_passed'] for x in r['trace']),
        supplemental_forward_bounds_passed=all(x['factor_gradient_roundoff']['component_bound_passed'] for x in r['trace']),
        waveform_maximum_error=max_wave,scalar_loss_maximum_error=max_loss,assessment=observed['assessment'],
        recovery_gates=dict(phase=bool(p95 <= plan['rules']['maximum_point_phase_p95_cycles']),
            root=bool(root_error <= plan['rules']['maximum_root_relative_p95']),
            support=fitted['observation_supported'],floor=fitted['original_scale_reached'],all_QPs=not failed),
        candidate_still_rejected=True,original_dense_started=False,full_goal_complete=False,
        limits=['Three isolated old QPs pass; changed nonlinear path still has three uncertified QPs, so recovery gates alone do not qualify it',
            'Do not select a truth-guided prefix or erase failures; no real DNA/runtime promotion',
            'Equivalent unit-box mapping and original full certificates reconstructed; original nearzero relative audit gate remains separately failed'])
except Exception as exc:
    r.update(result='failed',error=repr(exc)); raise
finally: save(args.out/'report.json',r)
print(json.dumps({k:r[k] for k in ('result','QPs_certified','QP_failure_steps','recovery_gates','geometry_maximum_relative_error')}),flush=True)
