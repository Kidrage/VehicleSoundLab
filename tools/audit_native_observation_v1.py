"""Reconstruct native-bin geometry, original QP certificates and full fit trace."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
    str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from absolute_amplitude_v1.amplitude import cost
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from joint_trust_v1.fit import scales_from_observation
from interior_qp_v1.backend import inequalities


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.native-observation-audit/1', result='running', sources={}, trace=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    value = load(args.candidate/'report.json')
    assert value['result'] in ('dense_native_observation_rejected', 'dense_native_observation_passed_not_full_qualification')
    assert value['parent_report_sha256'] == sha(args.parent/'report.json')
    certificate_path = repo/'tools/audit_interior_qp_v1.py'
    previous_audit = load(args.workspace/'references/analysis/interior_qp_v1/audit1/report.json')
    assert sha(certificate_path) == previous_audit['sources']['tools/audit_interior_qp_v1.py']
    tree = ast.parse(certificate_path.read_text(encoding='utf-8'))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == 'certificate')
    namespace = dict(np=np, linear_system=linear_system, inequalities=inequalities)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(certificate_path), 'exec'), namespace)
    certificate = namespace['certificate']
    sources = {Path(__file__), certificate_path} | {repo/name for name in value['sources']}
    for name, digest in value['sources'].items():
        assert sha(repo/name) == sha(args.candidate/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    old_plan, plan = load(args.parent/'effective_plan.json'), load(args.candidate/'effective_plan.json')
    assert {key: item for key, item in plan.items() if key != 'observed_order_step'} == {
        key: item for key, item in old_plan.items() if key != 'observed_order_step'}
    assert plan['observed_order_step'] == 1/plan['projection_cycles']
    settings = load(args.candidate/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    inputs = np.load(args.candidate/'input.npz')
    time, audio, initial = inputs['time'], inputs['audio'], inputs['initial_parameters']
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    case = next(item for item in topology['added_cases'] if item['id'] == 'unknown_thirty_six')
    independent_time, independent_audio, truth, _ = make(case, base)
    assert np.array_equal(time, independent_time) and np.array_equal(audio, independent_audio)
    old_saved = np.load(args.parent/'fit.npz')
    assert np.array_equal(initial, old_saved['initial_parameters'])
    model, old = (QuinticAbsoluteModel(time, setting, variant, []) for setting in (plan, old_plan))
    assert np.array_equal(model.original.phase_basis, old.original.phase_basis)
    assert np.array_equal(model.original.envelope_basis, old.original.envelope_basis)
    assert np.array_equal(model.original.samples(initial)[0], old.original.samples(initial)[0])
    operator, previous = model.original.aperture, old.original.aperture
    indices = np.searchsorted(operator.bins, previous.bins)
    native = operator.apply(audio[:, 0]).reshape(len(operator.starts), -1)
    coarse = previous.apply(audio[:, 0]).reshape(len(previous.starts), -1)
    assert np.array_equal(native[:, indices], coarse)
    # Independently evaluate every native bin at three time positions using
    # scalar global-time quadrature, not the FFT or geometry helper.
    window = np.sin(np.pi*np.arange(operator.size)/operator.size)**2
    maximum = 0.
    for row in (0, len(operator.starts)//2, len(operator.starts)-1):
        start = operator.starts[row]
        for col, order in enumerate(operator.orders):
            direct = 2*np.sum(audio[start:start+operator.size, 0]*window*
                np.exp(-2j*np.pi*order*time[start:start+operator.size]))/window.sum()
            maximum = max(maximum, float(abs(direct-native[row, col])))
    assert maximum < plan['rules']['maximum_forward_check_error']
    target = real_rows(operator.apply(audio[:, 0]))
    outer, amplitudes = model.unpack(initial)
    scales = scales_from_observation(model, outer, amplitudes, target, plan['soft_l1_scale'])
    fit = value['fit']
    assert np.array_equal(scales, np.asarray(fit['scales']))
    radius = settings['initial_radius']
    for row in fit['history']:
        assert radius == row['radius']
        prediction, derivative = model.prediction(outer, amplitudes, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
        residual = prediction-target
        assert cost(residual, plan['soft_l1_scale']) == row['before_cost']
        ratio = residual/plan['soft_l1_scale']
        curvature = (1+ratio**2)**(-1.5)
        gram = matrix.T@(curvature[:, None]*matrix)
        gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
        region = Region(model, outer, amplitudes, scales, radius, settings)
        checked = certificate(row['qp'], gram, gradient, region, np.sqrt(curvature)[:, None]*matrix)
        new_outer, new_amplitudes, effective, feasible = region.retract(np.asarray(row['qp']['primal_solution']))
        assert feasible == row['feasibility']
        assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_amplitudes, np.asarray(row['candidate_absolute_amplitudes']))
        candidate = cost(model.prediction(new_outer, new_amplitudes)-target, plan['soft_l1_scale'])
        predicted = float(-gradient@effective-.5*effective@gram@effective)
        actual = row['before_cost']-candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(feasible['feasible'] and predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
        assert candidate == row['candidate_cost'] and predicted == row['predicted_reduction']
        assert actual == row['actual_reduction'] and ratio == row['ratio'] and accepted == row['accepted']
        if accepted:
            outer, amplitudes = new_outer, new_amplitudes
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        report['trace'].append(dict(iteration=row['iteration'], accepted=accepted, certificate=checked,
            candidate_objective_retraction_radius_exact=True))
    assert radius == fit['final_radius']
    saved = np.load(args.candidate/'fit.npz')
    assert np.array_equal(model.pack(outer, amplitudes), saved['parameters'])
    _, phase, envelope = model.original.samples(saved['parameters'])
    assert np.array_equal(phase, saved['phase_correction'])
    assessment, positions, oracle = assess(audio, time, truth, phase, saved['parameters'],
        {**plan, 'heldout_orders': base['heldout_orders']})
    assert assessment == value['assessment']
    coordinates = np.load(args.candidate/'coordinates.npz')
    assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
    lower, upper = model.original.bounds(plan, variant)
    assert max(np.max(lower-saved['parameters']), np.max(saved['parameters']-upper)) <= 1e-9
    assert envelope.min() > 0 and np.diff(time+phase).min() > 0
    # Compare both saved estimators under both observation metrics, without
    # selecting either result or changing objective/regularization strength.
    costs = []
    for label, parameters in (('previous', old_saved['parameters']), ('native', saved['parameters'])):
        for name, local_model in (('previous', old), ('native', model)):
            local_target = real_rows(local_model.original.aperture.apply(audio[:, 0]))
            local_residual = local_model.original.prediction(parameters)-local_target
            costs.append(dict(parameters=label, observation=name,
                soft_l1_cost=cost(local_residual, plan['soft_l1_scale']),
                normalized_residual=float(np.linalg.norm(local_residual)/np.linalg.norm(local_target))))
    prior = args.workspace/'references/analysis/noise_budget_phase_v1/final1'
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/name).items())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    interior = (time >= 5)&(time < 35)
    fig, axis = plt.subplots(figsize=(10, 4), layout='constrained')
    for label, curve in (('Previous observations', old_saved['phase_correction']), ('All native bins', phase)):
        error = curve-truth
        error -= np.median(error[interior])
        axis.plot(time[interior], error[interior], label=label)
    for sign in (-1, 1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'], color='k', linestyle='--', linewidth=.7)
    axis.set(xlabel='Coarse-cycle coordinate', ylabel='Median-aligned phase error (cycles)')
    axis.legend()
    fig.savefig(args.out/'native_observation_phase.png', dpi=150)
    plt.close(fig)
    report.update(result='native_geometry_original_QP_certificates_and_full_trace_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), native_scalar_quadrature_maximum_error=maximum,
        original_observation_subset_exact=True, waveform_model_and_original_initial_exact=True,
        qp_certified=sum(row['certificate']['success'] for row in report['trace']),
        entire_trace_and_final_assessment_exact=True, cross_observation_costs=costs,
        plot_sha256=sha(args.out/'native_observation_phase.png'), C_H=540, voices_and_moving35_unchanged=True,
        full_qualification=False)
    print(json.dumps(dict(result=report['result'], qp_certified=report['qp_certified'], phase_p95=assessment['point_phase_p95_cycles'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
