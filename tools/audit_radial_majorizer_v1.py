"""Replay saved-parent deficits and all actual20 majorized restricted QPs."""
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
import scipy.sparse as sp
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from complex_radial_v1.loss import cost, hessian_apply, quadratic as old_quadratic
from complex_radial_v1.audit import explicit, relative
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from phase_envelope_blocks_v1.checks import certificate_function
from radial_majorizer_v1.audit import scalar_cost, geometry, independent_wave_and_jacobian


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sorted_scale(residual, floor):
    n = len(residual)//2; a = sorted(np.sqrt(residual[:n]**2+residual[n:]**2).tolist()); k = len(a)//2
    median = a[k] if len(a)%2 else .5*(a[k-1]+a[k])
    return max(floor, median), median


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.radial-majorizer-audit/1', result='running', sources={}, trace=[], parent_trace=[],
    real_audio_read=False, model_exported=False, runtime_changed=False, nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    root = args.workspace/'references/analysis/radial_majorizer_v1'; candidate = root/'fit1'
    observed = load(candidate/'report.json'); fitted = load(candidate/'fit.json')
    assert observed['result'] == 'known_majorizer_rejected' and observed['fit_report_sha256'] == sha(candidate/'fit.json')
    sources = {Path(__file__), repo/'tools/radial_majorizer_v1/audit.py', repo/'tools/complex_radial_v1/audit.py'}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(candidate/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][rel.as_posix()] = sha(path)
    r['candidate_report_sha256'] = sha(candidate/'report.json')
    certificate = certificate_function(repo/'tools/audit_interior_qp_v1.py')
    parent = args.workspace/'references/analysis/phase_envelope_blocks_v1/fit2'
    assert observed['parent_report_sha256'] == sha(parent/'report.json') and observed['parent_fit_sha256'] == sha(parent/'fit.json')
    previous = load(parent/'fit.json'); diagnosis = load(root/'diagnosis1/report.json')
    assert observed['diagnosis_report_sha256'] == sha(root/'diagnosis1/report.json')
    inputs = np.load(candidate/'input.npz'); original = np.load(parent/'input.npz')
    assert all(np.array_equal(inputs[k], original[k]) for k in inputs.files)
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(candidate/'effective_plan.json'), load(candidate/'effective_settings.json')
    assert plan == load(parent/'effective_plan.json') and settings == load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    target = real_rows(model.original.aperture.apply(audio[:, 0])); floor = plan['soft_l1_scale']
    scales = np.asarray(fitted['scales']); assert np.array_equal(scales, np.asarray(previous['scales']))
    outer, controls = model.unpack(initial)
    maximum_parent_error = 0.
    for saved, expected in zip(previous['history'], diagnosis['trace'], strict=True):
        value, derivative = model.prediction(outer, controls, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
        scalar_value, scalar_jacobian = independent_wave_and_jacobian(model, outer, controls)
        assert abs(value-scalar_value).max() < 1e-12 and relative(matrix, scalar_jacobian*scales) <= 1e-12
        new_outer, new_controls = np.asarray(saved['candidate_outer']), np.asarray(saved['candidate_absolute_amplitudes'])
        step = (np.r_[new_outer, new_controls.ravel()]-np.r_[outer, controls.ravel()])/scales
        residual = value-target; stage = saved['stage_scale']; gram, g, _, _ = old_quadratic(residual, matrix, stage)
        old_prediction = float(cost(residual, stage)+g@step+.5*step@gram@step)
        lin = residual+scalar_jacobian@(scales*step)
        actual = independent_wave_and_jacobian(model, new_outer, new_controls)[0]-target
        lin_cost, actual_cost = scalar_cost(lin, stage), scalar_cost(actual, stage)
        _, _, _, _, v = geometry(residual, matrix, stage)
        n = len(residual)//2; lin_power=lin[:n]**2+lin[n:]**2; power=residual[:n]**2+residual[n:]**2
        major = float(scalar_cost(residual, stage)+.5*np.sum(v*(lin_power-power)))
        fields = dict(before_cost=scalar_cost(residual, stage), old_quadratic_candidate=old_prediction,
            linearized_radial_candidate=lin_cost, actual_candidate=actual_cost,
            curvature_deficit=lin_cost-old_prediction, waveform_deficit=actual_cost-lin_cost,
            IRLS_majorizer_on_same_linear_step=major, majorizer_bound_margin=major-lin_cost)
        error = max(abs(fields[k]-expected[k]) for k in fields); maximum_parent_error=max(maximum_parent_error,error)
        assert error < 1e-12 and major >= lin_cost-1e-12
        r['parent_trace'].append(dict(iteration=saved['iteration'], maximum_absolute_error=error, scalar_reconstruction=True))
        if saved['accepted']: outer, controls = new_outer, new_controls
    outer, controls = model.unpack(initial); residual = model.prediction(outer, controls)-target
    stage, median = sorted_scale(residual, floor); assert abs(stage-fitted['initial_stage_scale']) < 1e-12
    value, jacobian = model.prediction(outer, controls, True); unscaled = np.column_stack((jacobian, model.design(outer)))
    factor = hessian_apply(value-target, unscaled, fitted['initial_stage_scale'], .5)
    independent_factor = explicit(value-target, unscaled, fitted['initial_stage_scale'])[2]
    assert relative(factor, independent_factor) <= 1e-12
    norms = np.linalg.norm(factor, axis=0)
    theta = np.minimum(1/np.maximum(norms[:len(outer)], 1e-30), np.r_[np.full(model.parts, np.pi), np.full(model.original.phase_count, model.phase_bound)])
    group = np.minimum(1/np.maximum(norms[len(outer):].reshape(controls.shape).max(axis=1), 1e-30), np.sqrt(2.))
    assert np.array_equal(scales, np.r_[theta, np.broadcast_to(group[:, None], controls.shape).ravel()])
    radius = settings['initial_radius']; maximum_geometry = maximum_wave = maximum_loss = 0.
    for index, row in enumerate(fitted['history'], 1):
        assert row['iteration'] == index and row['radius'] == radius
        active = np.arange(model.parts, len(outer)) if index%2 else np.r_[np.arange(model.parts), np.arange(len(outer), len(scales))]
        inactive = np.array([k for k in range(len(scales)) if k not in set(active)])
        qp = row['qp']; assert np.array_equal(active, qp['active_coordinates'])
        assert row['block'] == ('phase' if index%2 else 'angles_and_amplitude')
        value, jacobian = model.prediction(outer, controls, True)
        matrix = np.column_stack((jacobian, model.design(outer)))*scales[None, :]
        residual=value-target; stage=row['stage_scale']; expected_stage, expected_median=sorted_scale(residual,floor)
        assert abs(stage-expected_stage) < 1e-12 and abs(row['observed_residual_median']-expected_median) < 1e-12
        gram, g, weighted, errors, v = geometry(residual, matrix, stage); maximum_geometry=max(maximum_geometry,max(errors.values()))
        region = Region(model, outer, controls, scales, radius, settings)
        full_a, full_lo, full_hi = linear_system(region); dense=full_a.toarray()[:, active]
        keep=np.flatnonzero(np.any(dense != 0,axis=1)); removed=np.flatnonzero(np.all(dense == 0,axis=1))
        assert np.array_equal(keep,qp['retained_constraint_rows']) and np.all(full_lo[removed] <= 0) and np.all(full_hi[removed] >= 0)
        a,lo,hi=sp.csc_matrix(dense[keep]),full_lo[keep],full_hi[keep]
        checked=certificate(qp,gram[np.ix_(active,active)],g[active],(a,lo,hi),weighted[:,active])
        step=np.zeros(len(scales)); step[active]=qp['primal_solution']
        assert max(0.,np.max(full_lo-full_a@step),np.max(full_a@step-full_hi)) <= settings['maximum_primal_violation']
        y=np.zeros(len(full_lo)); y[keep]=qp['dual_solution']
        stationarity=(gram@step+g)/qp['objective_scale']+full_a.T@y
        assert float(abs(stationarity[inactive]).max()) == qp['inactive_stationarity_diagnostic']
        new_outer,new_controls,effective,feasible=region.retract(step)
        assert np.all(effective[inactive] == 0) and row['frozen_coordinate_step_error'] == 0.
        assert feasible == row['feasibility'] and np.array_equal(new_outer,row['candidate_outer'])
        assert np.array_equal(new_controls,row['candidate_absolute_amplitudes'])
        production=model.prediction(new_outer,new_controls)
        independent=independent_wave_and_jacobian(model,new_outer,new_controls)[0]
        wave_error=float(abs(production-independent).max()); maximum_wave=max(maximum_wave,wave_error); assert wave_error < 1e-12
        before,original_before=cost(residual,stage),cost(residual,floor)
        candidate_cost,original_candidate=cost(production-target,stage),cost(production-target,floor)
        loss_error=max(abs(scalar_cost(independent-target,stage)-candidate_cost),abs(scalar_cost(independent-target,floor)-original_candidate))
        maximum_loss=max(maximum_loss,loss_error); assert loss_error < 1e-12
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
        r['trace'].append(dict(iteration=index,block=row['block'],accepted=accepted,certificate=checked,
            geometry_errors=errors,linear_residual_majorizer_margin=bound_margin,
            full_original_constraints=True,zero_inactive_before_after=True,objectives_decisions_radius_exact=True))
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
    r.update(result='parent20_deficits_and_actual20_majorized_steps_independently_rebuilt',actual_QPs=20,
        restricted_QPs_certified=sum(x['certificate']['success'] for x in r['trace']),accepted_steps=sum(x['accepted'] for x in r['trace']),
        geometry_maximum_relative_error=maximum_geometry,waveform_maximum_error=maximum_wave,
        scalar_loss_maximum_error=maximum_loss,parent_deficit_maximum_error=maximum_parent_error,
        assessment=observed['assessment'],candidate_still_rejected=True,original_dense_started=False,full_goal_complete=False,
        limits=['Majorizer bounds linear residual cost; nonlinear-waveform acceptance still required',
            'One known case: all20 accepted repairs this path overshoot but not phase/support recovery or real timbre'])
except Exception as exc:
    r.update(result='failed',error=repr(exc)); raise
finally: save(args.out/'report.json',r)
print(json.dumps({k:r[k] for k in ('result','restricted_QPs_certified','accepted_steps','assessment','parent_deficit_maximum_error')}),flush=True)
