"""Independently replay coordinate restrictions and the complete saved path."""
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
from complex_radial_v1.loss import cost, hessian_apply
from complex_radial_v1.audit import check_geometry, explicit, relative
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from phase_envelope_blocks_v1.checks import certificate_function


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sorted_scale(residual, floor):
    n = len(residual)//2; values = sorted(np.sqrt(residual[:n]**2+residual[n:]**2).tolist())
    k = len(values)//2; median = values[k] if len(values)%2 else .5*(values[k-1]+values[k])
    return max(floor, median), median


def independent_wave(model, outer, controls):
    correction = model.original.phase_basis@outer[model.parts:]
    envelope = model.full@controls.T; wave = np.zeros(len(correction))
    for k, order in enumerate(model.original.orders):
        wave += envelope[:, k]*np.cos(2*np.pi*order*(model.original.time+correction)+outer[k])
    return wave


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.phase-envelope-blocks-audit/1', result='running', sources={}, trace=[],
    real_audio_read=False, model_exported=False, runtime_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    root = args.workspace/'references/analysis/phase_envelope_blocks_v1'; candidate = root/'fit2'
    observed = load(candidate/'report.json'); fitted = load(candidate/'fit.json')
    assert observed['result'] == 'known_blocks_rejected' and observed['fit_report_sha256'] == sha(candidate/'fit.json')
    source_paths = {Path(__file__), repo/'tools/complex_radial_v1/audit.py'}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(candidate/'exact_sources'/name) == digest
        source_paths.add(repo/name)
    for path in source_paths:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][rel.as_posix()] = sha(path)
    r['candidate_report_sha256'] = sha(candidate/'report.json')
    certificate = certificate_function(repo/'tools/audit_interior_qp_v1.py')
    # Retain/reproduce the original weakly-active analytic assertion failure from
    # its saved identical-control solution, with no additional solve.
    failure = load(root/'fit1/report.json'); replay = load(root/'control_failure_replay1.json')
    assert failure['result'] == 'failed' and failure['error'] == 'AssertionError()'
    old_checks = root/'fit1/exact_sources/tools/phase_envelope_blocks_v1/checks.py'
    assert sha(old_checks) == failure['sources']['tools/phase_envelope_blocks_v1/checks.py']
    assert 'error < 1e-7' in old_checks.read_text(encoding='utf-8')
    assert float(abs(np.asarray(replay['x'])-np.array([.5, -.25])).max()) == replay['maximum_coordinate_error'] > 1e-7
    assert observed['controls']['weakly_active_box_distance_bound']['original_1e7_coordinate_assertion_passed'] is False
    r['original_control_assertion_failure_preserved'] = dict(report_sha256=sha(root/'fit1/report.json'),
        replay_sha256=sha(root/'control_failure_replay1.json'), original_coordinate_gate_still_failed=True,
        separate_strong_convexity_gap_bound=observed['controls']['weakly_active_box_distance_bound'],
        solver_thresholds_changed=False, analytic_fixture_changed=False)
    parent = args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1'
    assert observed['joint_parent_report_sha256'] == sha(parent/'report.json')
    assert observed['joint_parent_fit_sha256'] == sha(parent/'fit.json')
    previous = load(parent/'fit.json')
    inputs = np.load(candidate/'input.npz'); original = np.load(parent/'input.npz')
    assert all(np.array_equal(inputs[k], original[k]) for k in inputs.files)
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(candidate/'effective_plan.json'), load(candidate/'effective_settings.json')
    assert plan == load(parent/'effective_plan.json') and settings == load(parent/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    outer, controls = model.unpack(initial); target = real_rows(model.original.aperture.apply(audio[:, 0]))
    floor = plan['soft_l1_scale']; residual = model.prediction(outer, controls)-target
    stage, median = sorted_scale(residual, floor)
    assert abs(stage-fitted['initial_stage_scale']) < 1e-12 and abs(median-fitted['initial_residual_median']) < 1e-12
    actual_scales = np.asarray(fitted['scales'])
    assert np.array_equal(actual_scales, np.asarray(previous['scales']))
    value, phase = model.prediction(outer, controls, True)
    matrix = np.column_stack((phase, model.design(outer)))
    factor = hessian_apply(value-target, matrix, fitted['initial_stage_scale'], .5)
    independent_factor = explicit(value-target, matrix, fitted['initial_stage_scale'])[2]
    assert relative(factor, independent_factor) <= 1e-12
    norms = np.linalg.norm(factor, axis=0)
    theta = np.minimum(1/np.maximum(norms[:len(outer)], 1e-30), np.r_[np.full(model.parts, np.pi), np.full(model.original.phase_count, model.phase_bound)])
    group = np.minimum(1/np.maximum(norms[len(outer):].reshape(controls.shape).max(axis=1), 1e-30), np.sqrt(2.))
    assert np.array_equal(actual_scales, np.r_[theta, np.broadcast_to(group[:, None], controls.shape).ravel()])
    radius = settings['initial_radius']; max_wave = max_loss = max_geometry = 0.
    for index, row in enumerate(fitted['history'], 1):
        assert row['iteration'] == index and row['radius'] == radius
        active = np.arange(model.parts, len(outer)) if index%2 else np.r_[np.arange(model.parts), np.arange(len(outer), len(actual_scales))]
        inactive = np.array([k for k in range(len(actual_scales)) if k not in set(active)])
        assert row['block'] == ('phase' if index%2 else 'angles_and_amplitude')
        qp = row['qp']; assert np.array_equal(active, qp['active_coordinates'])
        assert qp['certificate_scope'] == 'active_coordinates_only_other_coordinates_fixed_zero'
        value, phase = model.prediction(outer, controls, True)
        matrix = np.column_stack((phase, model.design(outer)))*actual_scales[None, :]
        residual = value-target; expected_stage, expected_median = sorted_scale(residual, floor)
        assert abs(row['stage_scale']-expected_stage) < 1e-12 and abs(row['observed_residual_median']-expected_median) < 1e-12
        stage = row['stage_scale']; gram, g, weighted, errors = check_geometry(residual, matrix, stage)
        max_geometry = max(max_geometry, max(errors.values()))
        region = Region(model, outer, controls, actual_scales, radius, settings)
        full_a, full_lo, full_hi = linear_system(region)
        # Independent dense structural inspection; no production restrict() call.
        dense = full_a.toarray()[:, active]; keep = np.flatnonzero(np.any(dense != 0, axis=1))
        removed = np.flatnonzero(np.all(dense == 0, axis=1))
        assert np.array_equal(keep, qp['retained_constraint_rows'])
        assert np.all(full_lo[removed] <= 0) and np.all(full_hi[removed] >= 0)
        a, lo, hi = sp.csc_matrix(dense[keep]), full_lo[keep], full_hi[keep]
        checked = certificate(qp, gram[np.ix_(active, active)], g[active], (a, lo, hi), weighted[:, active])
        local = np.asarray(qp['primal_solution']); step = np.zeros(len(actual_scales)); step[active] = local
        assert np.all(step[inactive] == 0)
        assert max(0., np.max(full_lo-full_a@step), np.max(full_a@step-full_hi)) <= settings['maximum_primal_violation']
        y = np.zeros(len(full_lo)); y[keep] = qp['dual_solution']
        stationarity = (gram@step+g)/qp['objective_scale']+full_a.T@y
        assert float(abs(stationarity[inactive]).max()) == qp['inactive_stationarity_diagnostic']
        new_outer, new_controls, effective, feasible = region.retract(step)
        assert np.all(effective[inactive] == 0) and row['frozen_coordinate_step_error'] == 0.
        assert feasible == row['feasibility'] and np.array_equal(new_outer, row['candidate_outer'])
        assert np.array_equal(new_controls, row['candidate_absolute_amplitudes'])
        production = model.prediction(new_outer, new_controls)
        independent = real_rows(model.original.aperture.apply(independent_wave(model, new_outer, new_controls)))
        wave_error = float(abs(production-independent).max()); max_wave = max(max_wave, wave_error); assert wave_error < 1e-12
        z = independent-target; n = len(z)//2; power = z[:n]**2+z[n:]**2
        scalar_stage = float(np.sum(power/(np.sqrt(1+power/stage**2)+1)))
        scalar_fixed = float(np.sum(power/(np.sqrt(1+power/floor**2)+1)))
        before, original_before = cost(residual, stage), cost(residual, floor)
        candidate_cost, original_candidate = cost(production-target, stage), cost(production-target, floor)
        loss_error = max(abs(scalar_stage-candidate_cost), abs(scalar_fixed-original_candidate)); max_loss = max(max_loss, loss_error)
        assert loss_error < 1e-12
        predicted = float(-g@effective-.5*effective@gram@effective)
        actual, original_actual = before-candidate_cost, original_before-original_candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(checked['success'] and feasible['feasible'] and predicted > 0 and actual > 0
            and ratio >= settings['acceptance_ratio'] and original_actual > 0)
        for key, expected in dict(before_cost=before, candidate_cost=candidate_cost, original_before_cost=original_before,
            original_candidate_cost=original_candidate, predicted_reduction=predicted, actual_reduction=actual,
            original_actual_reduction=original_actual, ratio=ratio, accepted=accepted).items(): assert row[key] == expected
        if accepted: outer, controls = new_outer, new_controls
        if not accepted or ratio < .25: radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius: radius = min(2*radius, settings['maximum_radius'])
        r['trace'].append(dict(iteration=index, block=row['block'], accepted=accepted, certificate=checked,
            geometry_errors=errors, full_original_constraints_passed=True, zero_inactive_before_after_retraction=True,
            wave_error=wave_error, scalar_loss_error=loss_error, objectives_decisions_radius_exact=True))
    parameters = model.pack(outer, controls); saved = np.load(candidate/'fit.npz')
    assert np.array_equal(parameters, saved['parameters']) and radius == fitted['final_radius']
    _, phase, envelope = model.original.samples(parameters); assert np.array_equal(phase, saved['phase_correction'])
    residual = model.original.prediction(parameters)-target
    assert cost(residual, floor) == fitted['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == fitted['normalized_projection_residual']
    stage, median = sorted_scale(residual, floor); assert abs(stage-fitted['final_stage_scale']) < 1e-12
    assert (stage == floor) == fitted['original_scale_reached']
    truth = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2); truth -= truth[0]
    inside = (time >= 5)&(time < 35); error = phase-truth; error -= np.median(error[inside])
    p95 = float(np.percentile(abs(error[inside]), 95))
    root_error = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/(1+np.gradient(truth, time))[inside], 95))
    assert p95 == observed['assessment']['phase_p95_cycles'] and root_error == observed['assessment']['root_relative_p95']
    assessed = np.load(candidate/'assessment.npz')
    assert np.array_equal(truth, assessed['true_phase']) and np.array_equal(error, assessed['phase_error'])
    r.update(result='all20_restricted_QPs_and_full_nonlinear_path_independently_rebuilt',
        actual_QPs=20, restricted_QPs_certified=sum(x['certificate']['success'] for x in r['trace']),
        phase_steps=10, angle_amplitude_steps=10, accepted_phase_steps=sum(x['accepted'] for x in r['trace'] if x['block'] == 'phase'),
        accepted_angle_amplitude_steps=sum(x['accepted'] for x in r['trace'] if x['block'] != 'phase'),
        geometry_maximum_relative_error=max_geometry, waveform_maximum_error=max_wave, scalar_loss_maximum_error=max_loss,
        assessment=observed['assessment'], candidate_still_rejected=True, original_dense_started=False, full_goal_complete=False,
        limits=['Certificates apply only to declared restricted QPs; inactive full gradients need not vanish',
            'One fixed schedule/input; reduced known error does not qualify real DNA or prove sole failure cause'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', r)
print(json.dumps({k: r[k] for k in ('result', 'restricted_QPs_certified', 'assessment', 'geometry_maximum_relative_error', 'waveform_maximum_error')}), flush=True)
