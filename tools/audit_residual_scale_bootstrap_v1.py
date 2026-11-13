"""Replay all stage/QP decisions and fixed variable-block counterfactuals, no fits."""
import argparse
import ast
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
from complex_radial_v1.loss import cost, quadratic, hessian_apply
from complex_radial_v1.audit import check_geometry, explicit, relative
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sorted_scale(residual, floor):
    n = len(residual)//2; values = np.sort(np.sqrt(residual[:n]**2+residual[n:]**2))
    k = len(values)//2
    median = float(values[k] if len(values)%2 else (values[k-1]+values[k])/2)
    return max(floor, median), median


def independent_wave(model, outer, controls):
    phase = model.original.phase_basis@outer[model.parts:model.parts+model.original.phase_count]
    envelope = model.full@controls.T
    result = np.zeros(len(phase))
    for k, order in enumerate(model.original.orders):
        angle = 2*np.pi*order*(model.original.time+phase)+outer[k]
        result += envelope[:, k]*np.cos(angle)
    return result


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.residual-scale-bootstrap-audit/1', result='running', sources={}, trace=[], block_comparisons=[],
    real_audio_read=False, model_exported=False, runtime_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    candidate = args.workspace/'references/analysis/residual_scale_bootstrap_v1/fit1'
    observed = load(candidate/'report.json'); assert observed['result'] == 'known_bootstrap_rejected'
    fitted = load(candidate/'fit.json'); assert observed['fit_report_sha256'] == sha(candidate/'fit.json')
    certificate_path = repo/'tools/audit_interior_qp_v1.py'
    old = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(certificate_path) == old['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(certificate_path.read_text(encoding='utf-8'))
    function = next(row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == 'certificate')
    ns = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(certificate_path), 'exec'), ns)
    sources = {Path(__file__), certificate_path, repo/'tools/complex_radial_v1/audit.py',
        repo/'research/residual_scale_bootstrap_v1_block_plan.json'}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(candidate/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][rel.as_posix()] = sha(path)
    report['candidate_report_sha256'] = sha(candidate/'report.json')
    inputs = np.load(candidate/'input.npz'); time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    parent = args.workspace/'references/analysis/orthogonal_band_v1/fit1/known'
    assert observed['parent_input_sha256'] == sha(parent/'input.npz')
    prior = np.load(parent/'input.npz'); assert all(np.array_equal(inputs[k], prior[k]) for k in inputs.files)
    plan, settings = load(candidate/'effective_plan.json'), load(candidate/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    outer, controls = model.unpack(initial); target = real_rows(model.original.aperture.apply(audio[:, 0]))
    floor = plan['soft_l1_scale']; residual = model.prediction(outer, controls)-target
    stage, median = sorted_scale(residual, floor)
    assert abs(stage-fitted['initial_stage_scale']) <= 1e-12 and abs(median-fitted['initial_residual_median']) <= 1e-12
    value, phase = model.prediction(outer, controls, True)
    matrix = np.column_stack((phase, model.design(outer)))
    # Exact helper arithmetic replays the certificate; independent2D factor checks units.
    actual_stage = fitted['initial_stage_scale']; weighted = hessian_apply(residual, matrix, actual_stage, .5)
    independent_factor = explicit(residual, matrix, actual_stage)[2]
    assert relative(weighted, independent_factor) <= 1e-12
    def scales(factor):
        norms = np.linalg.norm(factor, axis=0); m = model.original
        limits = np.r_[np.full(m.parts, np.pi), np.full(m.phase_count, model.phase_bound)]
        theta = np.minimum(1/np.maximum(norms[:len(outer)], 1e-30), limits)
        group = np.minimum(1/np.maximum(norms[len(outer):].reshape(controls.shape).max(axis=1), 1e-30), np.sqrt(2.))
        return np.r_[theta, np.broadcast_to(group[:, None], controls.shape).ravel()]
    actual_scales = scales(weighted); assert np.array_equal(actual_scales, np.asarray(fitted['scales']))
    report['independent_initial_scale_relative_error'] = relative(scales(independent_factor), actual_scales)
    radius = settings['initial_radius']; maximum_wave_error = maximum_loss_error = 0.
    for index, row in enumerate(fitted['history'], 1):
        assert row['iteration'] == index and row['radius'] == radius
        value, phase = model.prediction(outer, controls, True)
        matrix = np.column_stack((phase, model.design(outer)))*actual_scales[None, :]
        residual = value-target; expected_stage, expected_median = sorted_scale(residual, floor)
        assert abs(expected_stage-row['stage_scale']) <= 1e-12 and abs(expected_median-row['observed_residual_median']) <= 1e-12
        stage = row['stage_scale']; gram, g, weighted, errors = check_geometry(residual, matrix, stage)
        region = Region(model, outer, controls, actual_scales, radius, settings)
        checked = ns['certificate'](row['qp'], gram, g, region, weighted)
        new_outer, new_controls, effective, feasible = region.retract(np.asarray(row['qp']['primal_solution']))
        assert feasible == row['feasibility'] and np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_controls, np.asarray(row['candidate_absolute_amplitudes']))
        before, original_before = cost(residual, stage), cost(residual, floor)
        new_residual = model.prediction(new_outer, new_controls)-target
        candidate_cost, original_candidate = cost(new_residual, stage), cost(new_residual, floor)
        predicted = float(-g@effective-.5*effective@gram@effective)
        actual, original_actual = before-candidate_cost, original_before-original_candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(checked['success'] and feasible['feasible'] and predicted > 0 and actual > 0 and
            ratio >= settings['acceptance_ratio'] and original_actual > 0)
        for key, expected in dict(before_cost=before, candidate_cost=candidate_cost, original_before_cost=original_before,
                original_candidate_cost=original_candidate, predicted_reduction=predicted, actual_reduction=actual,
                original_actual_reduction=original_actual, ratio=ratio, accepted=accepted).items(): assert row[key] == expected
        comparisons = []
        for label in ('phase_only', 'angles_only', 'amplitude_only', 'full'):
            trial_outer = outer.copy(); trial_controls = controls.copy()
            if label in ('phase_only', 'full'): trial_outer[model.parts:] = new_outer[model.parts:]
            if label in ('angles_only', 'full'): trial_outer[:model.parts] = new_outer[:model.parts]
            if label in ('amplitude_only', 'full'): trial_controls = new_controls.copy()
            parameters = model.pack(trial_outer, trial_controls)
            low, high = model.original.bounds(plan, variant)
            clock = model.original.samples(parameters)[1]
            violation = float(max(0., np.max(low-parameters), np.max(parameters-high)))
            admissible = bool(violation <= 1e-9 and np.diff(time+clock).min() > 0)
            production = model.prediction(trial_outer, trial_controls)
            independent = real_rows(model.original.aperture.apply(independent_wave(model, trial_outer, trial_controls)))
            wave_error = float(abs(independent-production).max()); maximum_wave_error = max(maximum_wave_error, wave_error)
            assert wave_error < 1e-12
            z = independent-target; half = len(z)//2; power = z[:half]**2+z[half:]**2
            scalar_fixed = float(np.sum(power/(np.sqrt(1+power/floor**2)+1)))
            scalar_stage = float(np.sum(power/(np.sqrt(1+power/stage**2)+1)))
            fixed, staged = cost(production-target, floor), cost(production-target, stage)
            loss_error = max(abs(scalar_fixed-fixed), abs(scalar_stage-staged)); maximum_loss_error = max(maximum_loss_error, loss_error)
            assert loss_error < 1e-12
            comparisons.append(dict(block=label, admissible=admissible, original_bound_violation=violation,
                original_cost=fixed, original_reduction=original_before-fixed, stage_cost=staged,
                stage_reduction=before-staged, independent_wave_error=wave_error, independent_loss_error=loss_error))
        report['block_comparisons'].append(dict(iteration=index, full_accepted=accepted, original_before_cost=original_before,
            stage_before_cost=before, fixed_models=comparisons))
        if accepted: outer, controls = new_outer, new_controls
        if not accepted or ratio < .25: radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius: radius = min(2*radius, settings['maximum_radius'])
        report['trace'].append(dict(iteration=index, accepted=accepted, stage_scale=stage, certificate=checked,
            independent_geometry_errors=errors, dual_objectives_and_radius_exact=True))
        if index%5 == 0: print(json.dumps(dict(audited_step=index)), flush=True)
    parameters = model.pack(outer, controls); final = np.load(candidate/'fit.npz')
    assert np.array_equal(parameters, final['parameters']) and radius == fitted['final_radius']
    _, phase, envelope = model.original.samples(parameters); assert np.array_equal(phase, final['phase_correction'])
    residual = model.original.prediction(parameters)-target
    assert cost(residual, floor) == fitted['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == fitted['normalized_projection_residual']
    stage, median = sorted_scale(residual, floor)
    assert abs(stage-fitted['final_stage_scale']) < 1e-12 and abs(median-fitted['final_residual_median']) < 1e-12
    assert (stage == floor) == fitted['original_scale_reached']
    # Analytic truth is evaluation-only in the audit as well.
    truth = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2); truth -= truth[0]
    inside = (time >= 5)&(time < 35); error = phase-truth; error -= np.median(error[inside])
    p95 = float(np.percentile(abs(error[inside]), 95))
    root = float(np.percentile(abs(np.gradient(phase, time)-np.gradient(truth, time))[inside]/(1+np.gradient(truth, time))[inside], 95))
    assert p95 == observed['assessment']['phase_p95_cycles'] and root == observed['assessment']['root_relative_p95']
    assessment = np.load(candidate/'assessment.npz'); assert np.array_equal(truth, assessment['true_phase']) and np.array_equal(error, assessment['phase_error'])
    report.update(result='all20_stage_steps_and80_fixed_block_models_independently_rebuilt',
        original_fixed_cost_monotone_on_accepted_steps=True, original_dense_started=False,
        fixed_block_models=80, independent_wave_maximum_error=maximum_wave_error, independent_loss_maximum_error=maximum_loss_error,
        assessment=observed['assessment'], candidate_still_rejected=True, full_goal_complete=False,
        limits=['Fixed-block costs interact and are not additive source energies or optimal alternative paths',
            'No conclusion that initial robust curvature is the sole cause or that a better known cost is real timbre recovery'])
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally: save(args.out/'report.json', report)
