"""Reconstruct original SOCP KKT and all nonlinear noise-budget decisions."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--fits', nargs='+', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy.sparse as sp
from scipy.interpolate import BSpline
from scipy.optimize import brentq
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from joint_trust_v1.fit import scales_from_observation
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.backend import inequalities
from noise_budget_phase_v1.conic import solve


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def independent_controls(settings):
    # Ellipsoid projection with a scalar monotone multiplier equation.
    center, diagonal = np.array([2., 1.]), np.array([1., 2.])
    multiplier = brentq(lambda value: np.sum((diagonal*center/(1+value*diagonal**2))**2)-1, 0., 10.)
    expected = center/(1+multiplier*diagonal**2)
    x, evidence = solve(np.diag(diagonal), np.zeros(2), np.eye(2), -center,
        sp.eye(2, format='csc'), np.full(2, -4.), np.full(2, 4.), settings)
    first_error = float(abs(x-expected).max())
    first = dict(id='ellipsoid_scalar_multiplier', solution_error=first_error, original_solution_gate=1e-7,
        passed=bool(evidence['success'] and first_error < 1e-7), certificate=evidence)
    # Rectangular, rank-deficient data and an unpenalized third coordinate.
    target = np.array([2., -.5])
    expected = target/np.linalg.norm(target)
    matrix = np.array([[1., 0., 0.], [0., 1., 0.]])
    x, evidence = solve(matrix, np.zeros(2), matrix, -target,
        sp.eye(3, format='csc'), np.array([-4., -4., .25]), np.array([4., 4., .75]), settings)
    second_error = float(abs(x[:2]-expected).max())
    second = dict(id='rectangular_noise_and_unpenalized_nuisance', solution_error=second_error,
        original_solution_gate=1e-7, passed=bool(evidence['success'] and second_error < 1e-7 and .25 <= x[2] <= .75),
        certificate=evidence)
    # Preserve the failed control and its original threshold. Reconstruction
    # of saved actual evidence still proceeds; it does not qualify the solver.
    return dict(passed=first['passed'] and second['passed'], cases=[first, second],
        failed_controls_retained_without_relaxing_gates=True)


def original_certificate(saved, matrix, residual, rough, phase, region, settings):
    ranged, lower, upper = linear_system(region)
    rows, bounds, _, _ = inequalities(ranged, lower, upper)
    step = np.asarray(saved['primal_solution'])
    q, root = np.linalg.qr(np.column_stack((matrix, residual)), mode='reduced')
    beta = q@np.asarray(saved['compact_noise_dual_beta'])
    z, alpha = np.asarray(saved['inequality_dual']), saved['original_noise_dual_alpha']
    slack, data = bounds-rows@step, residual+matrix@step
    stationarity = float(abs(rough.T@(phase+rough@step)+rows.T@z-matrix.T@beta).max())
    primal = float(max(0., -slack.min(), np.linalg.norm(data)-1.))
    dual = float(max(0., -z.min(), np.linalg.norm(beta)-alpha))
    comp = float(max(abs(z*slack).max(), abs(alpha+beta@data)))
    valid = bool(primal <= settings['maximum_primal_violation'] and dual <= settings['maximum_primal_violation']
        and stationarity <= settings['maximum_normalized_stationarity'] and comp <= settings['maximum_complementarity'])
    certificate = dict(success=valid, primal=primal, dual_cone_violation=dual, original_stationarity=stationarity,
        complementarity=comp, original_noise_norm=float(np.linalg.norm(data)),
        objective=float(.5*np.linalg.norm(phase+rough@step)**2))
    assert certificate == saved['original_certificate']
    auxiliary = np.asarray(saved['auxiliary_solution'])
    equality_error = float(abs(phase+rough@step-auxiliary).max())
    auxiliary_error = float(abs(auxiliary-np.asarray(saved['equality_dual'])).max())
    assert equality_error == saved['equality_error'] and auxiliary_error == saved['auxiliary_stationarity']
    valid = valid and equality_error <= settings['maximum_primal_violation'] and auxiliary_error <= settings['maximum_normalized_stationarity']
    if 'acceptance_certificate' not in saved:
        valid = valid and saved['native_status'] == 'Solved'
    assert bool(valid) == saved['success']
    return certificate


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.noise-budget-phase-audit/1', result='running', sources={}, cases=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, actual_conic_subproblems_rerun=False, independent_conic_control_solves=True)
try:
    sources = {Path(__file__)}
    values = []
    historical = {'research/noise_budget_phase_v1_plan.json', 'tools/noise_budget_phase_v1/conic.py',
        'tools/noise_budget_phase_v1/fit.py', 'tools/diagnose_noise_budget_phase_v1.py'}
    for folder in args.fits:
        value = load(folder/'report.json')
        assert value['result'] in ('dense_noise_budget_candidate_rejected', 'dense_noise_budget_candidate_passed_not_full_qualification')
        changed = set()
        for name, digest in value['sources'].items():
            assert sha(folder/'exact_sources'/name) == digest
            if sha(repo/name) != digest:
                changed.add(name)
            sources.add(repo/name)
        assert changed in (set(), historical), changed
        values.append((folder, value, sorted(changed)))
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['independent_controls'] = independent_controls(load(args.fits[-1]/'effective_settings.json'))
    plotted = []
    for folder, value, changed in values:
        inputs = np.load(folder/'input.npz')
        time, audio, initial = inputs['time'], inputs['audio'], inputs['initial_parameters']
        noise_radius, roughness = float(inputs['noise_radius']), inputs['roughness']
        plan, settings = load(folder/'effective_plan.json'), load(folder/'effective_settings.json')
        variant = load(repo/'research/minority_phase_v1_plan.json')
        model = QuinticAbsoluteModel(time, plan, variant, [])
        outer, controls = model.unpack(initial)
        # Independent five-point exact quadrature, versus executed three-point.
        intervals = np.r_[0., np.arange(plan['phase_knot_cycles'], plan['cycles'], plan['phase_knot_cycles']), float(plan['cycles'])]
        knots = np.r_[[0.]*6, intervals[1:-1], [float(plan['cycles'])]*6]
        spline = BSpline(knots, np.eye(len(knots)-6), 5)
        nodes, weights = np.polynomial.legendre.leggauss(5)
        points = ((intervals[:-1]+intervals[1:])[:, None]/2+np.diff(intervals)[:, None]*nodes/2).ravel()
        measure = (np.diff(intervals)[:, None]*weights/2).ravel()
        independent = spline.derivative(3)(points)[:, 1:]*np.sqrt(measure)[:, None]
        first, count = model.parts, model.original.phase_count
        executed = roughness[:, first:first+count]*value['roughness']['objective_normalization']
        rough_gram_error = float(np.linalg.norm(independent.T@independent-executed.T@executed)/np.linalg.norm(independent.T@independent))
        assert rough_gram_error < 1e-12
        target = real_rows(model.original.aperture.apply(audio[:, 0]))
        scales = scales_from_observation(model, outer, controls, target, plan['soft_l1_scale'])
        assert np.array_equal(scales, np.asarray(value['fit']['scales']))
        radius, multiplier = settings['initial_radius'], 0.
        trace = []
        for row in value['fit']['history']:
            predicted, derivative = model.prediction(outer, controls, True)
            matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]/noise_radius
            residual = (predicted-target)/noise_radius
            rough = np.column_stack((roughness, np.zeros((len(roughness), controls.size))))*scales[None, :]
            phase = roughness@outer
            region = Region(model, outer, controls, scales, radius, settings)
            saved = row['subproblem']
            certificate = original_certificate(saved, matrix, residual, rough, phase, region, settings)
            new_outer, new_controls, effective, feasible = region.retract(np.asarray(saved['primal_solution']))
            assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
            assert np.array_equal(new_controls, np.asarray(row['candidate_absolute_amplitudes']))
            assert feasible == row['feasibility'] and radius == row['radius']
            multiplier = max(multiplier, settings['merit_dual_multiplier']*saved['original_noise_dual_alpha'])
            before = float(.5*np.dot(phase, phase))
            violation = float(max(0., np.linalg.norm(residual)-1))
            new_phase = roughness@new_outer
            after = float(.5*np.dot(new_phase, new_phase))
            linear_violation = float(max(0., np.linalg.norm(residual+matrix@effective)-1))
            actual_residual = (model.prediction(new_outer, new_controls)-target)/noise_radius
            actual_violation = float(max(0., np.linalg.norm(actual_residual)-1))
            expected = before+multiplier*violation-after-multiplier*linear_violation
            actual = before+multiplier*violation-after-multiplier*actual_violation
            ratio = actual/expected if expected > 0 else None
            accepted = bool(saved['success'] and feasible['feasible'] and expected > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
            exact = dict(merit_multiplier=multiplier, before_roughness=before, candidate_roughness=after,
                before_noise_violation=violation, candidate_noise_violation=actual_violation,
                linearized_noise_violation=linear_violation, predicted_reduction=expected,
                actual_reduction=actual, ratio=ratio, accepted=accepted, scaled_step_maximum=float(abs(effective).max()))
            assert all(row[key] == item for key, item in exact.items()), row['iteration']
            trace.append(dict(iteration=row['iteration'], original_certificate=certificate,
                native_status=saved['native_status'], accepted=accepted, candidate_merit_noise_radius_exact=True))
            if accepted:
                outer, controls = new_outer, new_controls
            if not accepted or ratio < .25:
                radius *= .25
            elif ratio > .75 and abs(effective).max() > .8*radius:
                radius = min(2*radius, settings['maximum_radius'])
        saved = np.load(folder/'fit.npz')
        parameters = model.pack(outer, controls)
        _, phase, _ = model.original.samples(parameters)
        assert np.array_equal(parameters, saved['parameters']) and np.array_equal(phase, saved['phase_correction'])
        assert radius == value['fit']['final_radius'] and multiplier == value['fit']['final_merit_multiplier']
        parent = args.workspace/'references/analysis/interior_qp_v1/fit1'
        truth = np.load(parent/'fit.npz')['true_phase_correction']
        assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
            {**plan, 'heldout_orders': load(repo/'research/aperture_model_v1_plan.json')['heldout_orders']})
        assert assessment == value['assessment']
        coordinates = np.load(folder/'coordinates.npz')
        assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
        report['cases'].append(dict(fit=folder.name, report_sha256=sha(folder/'report.json'),
            historical_changed_sources=changed, roughness_five_point_Gram_relative_error=rough_gram_error,
            all_candidates_merit_noise_radius_and_final_assessment_exact=True,
            original_conic_certificates_passed=sum(row['original_certificate']['success'] for row in trace), trace=trace))
        plotted.append((folder.name, time, phase, truth, value['fit']))
    prior = args.workspace/'references/analysis/bounded_phase_noise_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/name).items())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
    for name, time, phase, truth, fit in plotted:
        interior = (time >= 5)&(time < 35)
        error = phase-truth
        error -= np.median(error[interior])
        axes[0].plot(time[interior], error[interior], label=name)
        axes[1].plot([row['iteration'] for row in fit['history']],
            [1+row['candidate_noise_violation'] for row in fit['history']], '.-', label=name+' candidates')
    for sign in (-1, 1):
        axes[0].axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'], color='k', linestyle='--', linewidth=.7)
    axes[0].set(xlabel='Coarse-cycle coordinate', ylabel='Median-aligned phase error (cycles)')
    axes[1].set(xlabel='Nonlinear iteration', ylabel='1 + candidate noise-budget excess')
    for axis in axes:
        axis.legend()
    fig.savefig(args.out/'noise_budget_phase.png', dpi=150)
    plt.close(fig)
    report.update(result='original_conic_certificates_and_full_noise_budget_traces_reconstructed',
        plot_sha256=sha(args.out/'noise_budget_phase.png'), C_H=540, voices_and_moving35_unchanged=True,
        independent_solver_controls_qualified=report['independent_controls']['passed'],
        full_qualification=False)
    print(json.dumps(dict(result=report['result'], cases=[dict(fit=row['fit'], original_certified=row['original_conic_certificates_passed'])
        for row in report['cases']])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
