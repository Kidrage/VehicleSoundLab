"""Reconstruct the observed migration and complete saved quintic trust trace."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
sys.path.insert(0, str(args.workspace/'tools/qp_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from positive_band_envelope_v1.model import BandModel
from quintic_phase_v1.model import QuinticAbsoluteModel
from absolute_amplitude_v1.amplitude import cost
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess
from observed_topology_v1.fixtures import make
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from joint_trust_v1.fit import scales_from_observation


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump_ast(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.quintic-phase-audit/1', result='running', sources={}, trace=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, migration_solver_rerun=False)
try:
    value = load(args.candidate/'report.json')
    assert value['result'] in ('dense_diagnostic_rejected', 'dense_diagnostic_passed_not_full_qualification')
    report['candidate_report_sha256'] = sha(args.candidate/'report.json')
    source = {Path(__file__)}
    for relative, digest in value['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        source.add(repo/relative)
    for path in source:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)

    # Verify the old cubic entry retains exactly the old numerical loop. The
    # new entry injects a model; it does not modify the trust-region equations.
    old_fit = args.workspace/'references/analysis/joint_trust_v1/dense2/exact_sources/tools/joint_trust_v1/fit.py'
    old_report = load(args.workspace/'references/analysis/joint_trust_v1/dense2/report.json')
    assert sha(old_fit) == old_report['sources']['tools/joint_trust_v1/fit.py']
    old_ast = ast.parse(old_fit.read_text(encoding='utf-8'))
    new_ast = ast.parse((repo/'tools/joint_trust_v1/fit.py').read_text(encoding='utf-8'))
    old_estimate = next(n for n in old_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'estimate')
    new_estimate = next(n for n in new_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'estimate_with_model')
    assert dump_ast(old_estimate.body[1:]) == dump_ast(new_estimate.body[1:])
    old_scales = next(n for n in old_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'scales_from_observation')
    new_scales = next(n for n in new_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'scales_from_observation')
    assert ast.dump(old_scales, include_attributes=False) == ast.dump(new_scales, include_attributes=False)
    report['shared_fit_refactor'] = dict(previous_source_sha256=sha(old_fit),
        numerical_loop_AST_exact=True, observation_scaling_AST_exact=True,
        model_injection_only=True, old_stage_source_changed_not_rewritten=True)

    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    variant = load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    plan = load(args.candidate/'effective_plan.json')
    settings = load(repo/'research/joint_trust_precise_v1_plan.json')
    saved = np.load(args.candidate/'fit.npz')
    assert np.array_equal(saved['time'], time) and np.array_equal(saved['true_phase_correction'], truth)
    assert value['fit']['selected_indices'] == []
    model = QuinticAbsoluteModel(time, plan, variant, [])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))

    # Independent bounded-least-squares optimality audit: no migration refit and
    # no use of analytic fixture phase. The input is the previous observed fit.
    old_model = BandModel(time, plan, variant, [])
    old = saved['previous_parameters']
    initial = saved['initial_parameters']
    count = 2*model.parts
    assert np.array_equal(initial[:count], old[:count])
    assert np.array_equal(initial[count+model.original.phase_count:model.original.base_count],
        old[count+old_model.phase_count:old_model.base_count])
    assert np.array_equal(initial[model.original.base_count:], old[old_model.base_count:])
    observed_phase = old_model.phase_basis@old[count:count+old_model.phase_count]
    controls0 = initial[count:count+model.original.phase_count]
    migrated_phase = model.original.phase_basis@controls0
    migration_residual = migrated_phase-observed_phase
    migration_gradient = model.original.phase_basis.T@migration_residual
    bound = plan['phase_control_bound_cycles']
    projected = controls0-np.clip(controls0-migration_gradient, -bound, bound)
    kkt = float(abs(projected).max())
    assert kkt < 1e-9
    migration = load(args.candidate/'initialization.json')
    assert float(abs(migration_residual).max()) == migration['maximum_phase_migration_error']
    assert float(np.sqrt(np.mean(migration_residual**2))) == migration['rms_phase_migration_error']
    old_wave = old_model.samples(old)[0]
    new_wave = model.original.samples(initial)[0]
    assert float(abs(old_wave-new_wave).max()) == migration['maximum_waveform_migration_error']
    report['observed_migration'] = dict(original_coefficients_amplitudes_minorities_exact=True,
        maximum_phase_error=migration['maximum_phase_migration_error'],
        maximum_waveform_error=migration['maximum_waveform_migration_error'],
        bounded_LS_projected_gradient=kkt, truth_used=False, heldout_used=False,
        exact_migration_claimed=False)

    parameters = saved['parameters']
    _, phase, envelope = model.original.samples(parameters)
    assert np.array_equal(phase, saved['phase_correction'])
    assessment, positions, oracle = assess(audio, time, truth, phase, parameters,
        {**plan, 'heldout_orders': base['heldout_orders']})
    assert assessment == value['assessment']
    coordinates = np.load(args.candidate/'coordinates.npz')
    assert np.array_equal(positions, coordinates['positions']) and np.array_equal(oracle, coordinates['oracle_positions'])
    residual = model.original.prediction(parameters)-target
    assert cost(residual, plan['soft_l1_scale']) == value['fit']['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == value['fit']['normalized_projection_residual']
    low, high = model.original.bounds(plan, variant)
    bound_error = float(max(0., np.max(low-parameters), np.max(parameters-high)))
    assert bound_error <= 1e-9 and envelope.min() > 0

    outer, controls = model.unpack(initial)
    scales = np.asarray(value['fit']['scales'])
    assert np.array_equal(scales, scales_from_observation(model, outer, controls, target, plan['soft_l1_scale']))
    radius = settings['initial_radius']
    for row in value['fit']['history']:
        assert radius == row['radius']
        predicted, derivative = model.prediction(outer, controls, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
        residual = predicted-target
        before = cost(residual, plan['soft_l1_scale'])
        assert before == row['before_cost']
        ratio = residual/plan['soft_l1_scale']
        curvature = (1+ratio**2)**(-1.5)
        gram = matrix.T@(curvature[:, None]*matrix)
        gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
        region = Region(model, outer, controls, scales, radius, settings)
        linear, lower, upper = linear_system(region)
        qp = row['qp']
        x, y = np.asarray(qp['primal_solution']), np.asarray(qp['dual_solution'])
        objective_scale = max(float(abs(gradient).max()), np.finfo(float).tiny)
        assert objective_scale == qp['objective_scale']
        normal = (gram+gram.T)/(2*objective_scale)
        stationarity = float(abs(normal@x+gradient/objective_scale+linear.T@y).max())
        observed = linear@x
        primal = float(max(0., np.max(lower-observed), np.max(observed-upper)))
        assert stationarity == qp['normalized_dual_stationarity'] and primal == qp['constraint_violation']
        certified = bool(qp['status_value'] == 1 and primal <= 1e-9 and stationarity <= 1e-8)
        assert certified == qp['success']
        new_outer, new_controls, effective, feasible = region.retract(x)
        assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_controls, np.asarray(row['candidate_absolute_amplitudes']))
        assert feasible == row['feasibility']
        candidate_cost = cost(model.prediction(new_outer, new_controls)-target, plan['soft_l1_scale'])
        predicted_reduction = float(-gradient@effective-.5*effective@gram@effective)
        actual = before-candidate_cost
        step_ratio = actual/predicted_reduction if predicted_reduction > 0 else None
        assert candidate_cost == row['candidate_cost'] and step_ratio == row['ratio']
        assert predicted_reduction == row['predicted_reduction'] and actual == row['actual_reduction']
        accept = bool(feasible['feasible'] and predicted_reduction > 0 and actual > 0
            and step_ratio >= settings['acceptance_ratio'])
        assert accept == row['accepted']
        report['trace'].append(dict(iteration=row['iteration'], primal=primal, stationarity=stationarity,
            qp_certified=certified, qp_iterations=qp['iterations'], accepted=accept,
            all_candidate_objective_and_decision_values_exact=True))
        if accept:
            outer, controls = new_outer, new_controls
        if not accept or step_ratio < .25:
            radius *= .25
        elif step_ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
    assert radius == value['fit']['final_radius']
    assert np.array_equal(model.pack(outer, controls), parameters)
    assert len(report['trace']) == value['fit']['iterations']
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        path = args.workspace/'references/analysis/absolute_amplitude_v1/final1'/filename
        assert all(sha(repo/name) == digest for name, digest in load(path).items())
    report.update(result='reconstructed_quintic_candidate_migration_and_entire_trace',
        assessment=assessment, original_bound_error=bound_error, entire_trace_exact=True,
        accepted_steps=sum(r['accepted'] for r in report['trace']),
        qp_certified=sum(r['qp_certified'] for r in report['trace']),
        qp_uncertified=sum(not r['qp_certified'] for r in report['trace']),
        C_H=540, voices_and_moving35_unchanged=True,
        limits=['Numerical reconstruction is not real-engine or full33/14kHz qualification',
            'Bounded migration is an approximation; original cubic and quintic spaces are not nested'])
    print(json.dumps({k: report[k] for k in ('result', 'accepted_steps', 'qp_certified', 'qp_uncertified', 'assessment')}), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
