"""Independently reconstruct saved QP certificates and full nonlinear trace."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--fit', type=Path, required=True)
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


def merged(path):
    values = []
    while True:
        value = load(path)
        values.append(value)
        if path == repo/'research/joint_trust_precise_v1_plan.json':
            break
        path = repo/value['parent_plan']
    result = {}
    for value in reversed(values):
        result.update(value)
    return result


def certificate(qp, gram, gradient, region, weighted):
    matrix, lower, upper = linear_system(region)
    rows, bounds, high, low = inequalities(matrix, lower, upper)
    x, y, z = np.asarray(qp['primal_solution']), np.asarray(qp['dual_solution']), np.asarray(qp['inequality_dual'])
    mapped = np.zeros(len(lower))
    mapped[high] += z[:len(high)]
    mapped[low] -= z[len(high):]
    assert np.array_equal(mapped, y)
    scale = max(float(abs(gradient).max()), np.finfo(float).tiny)
    assert scale == qp['objective_scale']
    normal = (gram+gram.T)/(2*scale)
    observed = matrix@x
    primal = float(max(0., np.max(lower-observed), np.max(observed-upper)))
    dual = float(abs(normal@x+gradient/scale+matrix.T@y).max())
    sign = float(max(0., -z.min()))
    complementarity = float(abs(z*(bounds-rows@x)).max())
    assert primal == qp['constraint_violation'] and dual == qp['normalized_dual_stationarity']
    assert sign == qp['inequality_dual_sign_violation'] and complementarity == qp['maximum_complementarity']
    assert float(.5*x@gram@x+gradient@x) == qp['objective']
    solved = qp['status'] in ('Solved', 'SolvedActiveSet')
    if qp['status'] == 'SolvedActiveSet':
        assert qp['active_set_polish']['success'] and qp['active_set_polish']['attempted']
        assert qp['termination'] == 'independent_original_KKT_certificate'
    success = bool(solved and primal <= 1e-9 and dual <= 1e-8 and sign <= 1e-9 and complementarity <= 1e-8)
    assert success == qp['success']
    result = dict(success=success, primal=primal, stationarity=dual, dual_sign=sign,
        complementarity=complementarity, original_objective=qp['objective'], status=qp['status'])
    if 'auxiliary_solution' in qp:
        root = np.linalg.qr(weighted, mode='r')/np.sqrt(scale)
        auxiliary = np.asarray(qp['auxiliary_solution'])
        equality_dual = np.asarray(qp['equality_dual'])
        assert float(abs(root@x-auxiliary).max()) == qp['maximum_lifted_equality_error']
        assert float(abs(auxiliary-equality_dual).max()) == qp['maximum_auxiliary_stationarity']
        result['lifted_equalities_reconstructed'] = True
    if 'coarse_attempt' in qp:
        result['coarse'] = certificate(qp['coarse_attempt'], gram, gradient, region, weighted)
    if qp.get('precision_refinement', {}).get('attempted'):
        p = qp['precision_refinement']
        coarse = qp['coarse_attempt']
        excess = max(1., coarse['normalized_dual_stationarity']/1e-8,
            coarse['constraint_violation']/1e-9, coarse['maximum_complementarity']/1e-8)
        assert excess == p['certificate_excess_ratio']
        assert max(p['minimum_tolerance'], p['original_tolerance']/(p['safety_divisor']*excess)) == p['refined_tolerance']
    return result


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.interior-qp-audit/1', result='running', sources={}, replay_certificates=[], trace=[],
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False, active_set_solver_rerun=False)
try:
    parent, value = load(args.parent/'report.json'), load(args.fit/'report.json')
    assert value['result'] in ('dense_diagnostic_rejected', 'dense_diagnostic_passed_not_full_qualification')
    assert value['parent_report_sha256'] == sha(args.parent/'report.json')
    report['fit_report_sha256'] = sha(args.fit/'report.json')
    sources = {Path(__file__)} | {repo/name for name in value['sources']}
    for name, digest in value['sources'].items():
        assert sha(repo/name) == sha(args.fit/'exact_sources'/name) == digest
    for path in sources:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base, variant = load(repo/topology['base_plan']), load(repo/topology['minority_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, audio, truth, _ = make(case, base)
    plan = load(args.fit/'effective_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    settings = merged(repo/'research/certified_qp_v1_plan.json')
    saved, old = np.load(args.fit/'fit.npz'), np.load(args.parent/'fit.npz')
    assert np.array_equal(time, saved['time']) and np.array_equal(truth, saved['true_phase_correction'])
    assert np.array_equal(saved['initial_parameters'], old['initial_parameters'])
    scales = np.asarray(value['fit']['scales'])
    initial_outer, initial_absolute = model.unpack(saved['initial_parameters'])
    assert np.array_equal(scales, scales_from_observation(model, initial_outer, initial_absolute, target, plan['soft_l1_scale']))

    def geometry(outer, absolute, radius, local_scales):
        predicted, derivative = model.prediction(outer, absolute, True)
        matrix = np.column_stack((derivative, model.design(outer)))*local_scales[None, :]
        residual = predicted-target
        ratio = residual/plan['soft_l1_scale']
        curvature = (1+ratio**2)**(-1.5)
        gram = matrix.T@(curvature[:, None]*matrix)
        gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
        return residual, gram, gradient, Region(model, outer, absolute, local_scales, radius, settings), np.sqrt(curvature)[:, None]*matrix

    # Compare all recorded actual replays, including failures, without solving.
    for folder in ('replay1', 'replay_qr1', 'replay_refined2', 'replay_certified2'):
        root = args.fit.parent/folder
        evidence = load(root/'report.json')
        for item in evidence['replays']:
            iteration = item['iteration']
            if iteration == 1:
                outer, absolute = model.unpack(old['initial_parameters'])
            else:
                prior = parent['fit']['history'][iteration-2]
                assert prior['accepted']
                outer, absolute = np.asarray(prior['candidate_outer']), np.asarray(prior['candidate_absolute_amplitudes'])
            _, gram, gradient, region, weighted = geometry(outer, absolute, item['radius'], np.asarray(parent['fit']['scales']))
            checked = certificate(item['new_QP'], gram, gradient, region, weighted)
            report['replay_certificates'].append(dict(folder=folder, iteration=iteration, certificate=checked))

    outer, absolute = initial_outer, initial_absolute
    radius = settings['initial_radius']
    for row in value['fit']['history']:
        assert row['radius'] == radius
        residual, gram, gradient, region, weighted = geometry(outer, absolute, radius, scales)
        assert cost(residual, plan['soft_l1_scale']) == row['before_cost']
        checked = certificate(row['qp'], gram, gradient, region, weighted)
        new_outer, new_absolute, effective, feasible = region.retract(np.asarray(row['qp']['primal_solution']))
        assert feasible == row['feasibility']
        assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_absolute, np.asarray(row['candidate_absolute_amplitudes']))
        candidate = cost(model.prediction(new_outer, new_absolute)-target, plan['soft_l1_scale'])
        predicted = float(-gradient@effective-.5*effective@gram@effective)
        actual = row['before_cost']-candidate
        ratio = actual/predicted if predicted > 0 else None
        assert candidate == row['candidate_cost'] and predicted == row['predicted_reduction']
        assert actual == row['actual_reduction'] and ratio == row['ratio']
        accepted = bool(feasible['feasible'] and predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
        assert accepted == row['accepted']
        if accepted:
            outer, absolute = new_outer, new_absolute
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        report['trace'].append(dict(iteration=row['iteration'], accepted=accepted,
            certificate=checked, candidate_objective_retraction_radius_exact=True))
    assert np.array_equal(model.pack(outer, absolute), saved['parameters'])
    assert radius == value['fit']['final_radius']
    _, phase, envelope = model.original.samples(saved['parameters'])
    assert np.array_equal(phase, saved['phase_correction'])
    assessment, positions, oracle = assess(audio, time, truth, phase, saved['parameters'],
        {**plan, 'heldout_orders': base['heldout_orders']})
    assert assessment == value['assessment']
    coordinate = np.load(args.fit/'coordinates.npz')
    assert np.array_equal(positions, coordinate['positions']) and np.array_equal(oracle, coordinate['oracle_positions'])
    residual = model.original.prediction(saved['parameters'])-target
    assert cost(residual, plan['soft_l1_scale']) == value['fit']['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == value['fit']['normalized_projection_residual']
    low, high = model.original.bounds(plan, variant)
    assert max(np.max(low-saved['parameters']), np.max(saved['parameters']-high)) <= 1e-9
    assert envelope.min() > 0 and np.diff(time+phase).min() > 0
    prior = args.workspace/'references/analysis/quintic_phase_v1/final1'
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/name) == digest for name, digest in load(prior/filename).items())
    report.update(result='reconstructed_original_QP_certificates_and_full_trace',
        entire_trace_exact=True, final_assessment_exact=True, assessment=assessment,
        qp_certified=sum(row['certificate']['success'] for row in report['trace']),
        qp_uncertified=sum(not row['certificate']['success'] for row in report['trace']),
        C_H=540, voices_and_moving35_unchanged=True)
    print(json.dumps(dict(result=report['result'], trace=len(report['trace']),
        qp_certified=report['qp_certified'], qp_uncertified=report['qp_uncertified'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
