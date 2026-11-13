"""Rebuild saved QPs and every blocking move; never re-solve a QP."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import scipy.linalg as la
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from orthogonal_band_v1.operator import OrthogonalBand
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from joint_trust_v1.osqp_backend import linear_system
from joint_radial_majorizer_v1.audit import geometry


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def measure(h, g, rows, bounds, x, z):
    normal = h@x+g+rows.T@z
    slack = bounds-rows@x
    return dict(primal=float(max(0., -slack.min())), stationarity=float(abs(normal).max()),
        dual_sign=float(max(0., -z.min())), complementarity=float(abs(z*slack).max()))


def passed(q):
    return bool(q['primal'] <= 1e-9 and q['stationarity'] <= 1e-8
        and q['dual_sign'] <= 1e-9 and q['complementarity'] <= 1e-8)


def inspect_path(gram, gradient, weighted, rhs, rows, bounds, initial, details):
    scale = float(abs(gradient).max()) or max(float(abs(gram).max()), 1.)
    h, g = (gram+gram.T)/(2*scale), gradient/scale
    x = initial.copy(); contact = np.flatnonzero(bounds-rows@x <= 1e-9).tolist()
    maximum = 0.; minima = []; trace = []
    assert len(details['history']) == details['iterations'] <= 20
    for index, row in enumerate(details['history'], 1):
        assert row['iteration'] == index and np.array_equal(x, row['start'])
        before = row['working_before']; assert set(before).issubset(contact)
        # Independent SVD checks row-span preservation, not the QR pivot order.
        if contact:
            coefficients = la.lstsq(rows[before].T, rows[contact].T, lapack_driver='gelsd')[0]
            span_error = float(abs(rows[before].T@coefficients-rows[contact].T).max())
            assert span_error <= 1e-12
        else:
            span_error = 0.; assert not before
        minimum = np.array(row['equality_minimum']); direction = minimum-x
        equality_error = float(abs(rows[before]@minimum-bounds[before]).max()) if before else 0.
        assert equality_error <= 1e-9
        # Verify the saved equality minimum's LS first-order residual using
        # SVD multipliers. This is a backward check, not another QP solution.
        residual = weighted@minimum-rhs
        derivative = weighted.T@residual
        if before:
            multiplier = la.lstsq(rows[before].T, -derivative, lapack_driver='gelsd')[0]
            error = derivative+rows[before].T@multiplier
        else:
            error = derivative
        backward = float(np.linalg.norm(error)/max(np.linalg.norm(weighted)*np.linalg.norm(residual), 1e-300))
        assert backward <= 1e-10
        alpha = row['fraction']; assert 0 <= alpha <= 1
        next_x = minimum if alpha == 1 else x+alpha*direction
        assert np.array_equal(next_x, row['primal_solution'])
        # All inequalities, not just working faces, must survive the path.
        primal = float(max(0., np.max(rows@next_x-bounds))); assert primal <= 1e-9
        gamma = len(next_x)*np.finfo(float).eps/(1-len(next_x)*np.finfo(float).eps)
        dot_bound = gamma*float(np.max(np.asarray(abs(rows), dtype=np.longdouble)@np.asarray(abs(next_x), dtype=np.longdouble)))
        assert primal+dot_bound <= 1e-9
        maximum = max(maximum, primal)
        projected = rows@direction; slack = bounds-rows@x
        eligible = [j for j in range(len(bounds)) if j not in set(before) and projected[j] > 0]
        fractions = [(max(0., float(slack[j]))/float(projected[j]), j) for j in eligible]
        smallest, first = min(fractions, default=(math.inf, -1))
        assert alpha == min(1., smallest)
        contact = before.copy()
        if alpha < 1:
            assert row['blocker'] == first
            contact.append(first)
        else:
            assert row['blocker'] is None
        assert contact == row['working_after_move']
        z = np.array(row['inequality_dual'])
        assert np.count_nonzero(np.delete(z, contact)) == 0
        q = measure(h, g, rows, bounds, next_x, z)
        assert q == row['certificate'] and passed(q) == row['success']
        if row['success']:
            assert row['action'] == 'certify' and index == len(details['history'])
        elif alpha < 1:
            assert row['action'] == 'first_blocker'
        elif contact and min(z[contact]) < -1e-9:
            drop = int(np.argmin(z[contact])); assert row['action'] == 'drop_negative_dual'
            assert row['dropped'] == contact[drop]; contact.pop(drop)
        else:
            assert row['action'] == 'full_minimum_uncertified' and index == len(details['history'])
        trace.append(dict(iteration=index, original_certificate=q, row_span_error=span_error,
            equality_error=equality_error, equality_minimum_relative_backward_error=backward,
            scalar_roundoff_primal_upper_bound=primal+dot_bound,
            all_inequalities_feasible=True, blocking_fraction_exact=True, action=row['action']))
        minima.append(backward); x = next_x
    assert passed(q) == details['success']
    # Independent scalar sums of the final full KKT, including cancellation.
    scalar_normal = np.array([math.fsum([*(float(a)*float(b) for a, b in zip(row, x)),
        float(g[i]), *(float(a)*float(b) for a, b in zip(rows[:, i], z))]) for i, row in enumerate(h)])
    scalar_slack = np.array([float(bound)-math.fsum(float(a)*float(b) for a, b in zip(row, x)) for row, bound in zip(rows, bounds)])
    scalar = dict(primal=float(max(0., -scalar_slack.min())), stationarity=float(abs(scalar_normal).max()),
        dual_sign=float(max(0., -z.min())), complementarity=float(abs(z*scalar_slack).max()))
    assert passed(scalar) == details['success']
    return dict(success=details['success'], iterations=len(trace), maximum_path_primal=maximum,
        final_scalar_certificate=scalar, trace=trace)


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.feasible-polish-audit/1', result='running', sources={}, replays=[],
    truth_read=False, nonlinear_estimator_rerun=False, quadratic_solver_rerun=False,
    active_set_solver_rerun=False, real_audio_read=False, runtime_changed=False)
try:
    candidate = args.workspace/'references/analysis/feasible_polish_v1/replay1'
    observed = load(candidate/'report.json'); assert observed['result'] == 'feasible_polish_replay_rejected'
    sources = {Path(__file__), repo/'tools/joint_radial_majorizer_v1/audit.py'}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(candidate/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][rel.as_posix()] = sha(path)
    r['candidate_report_sha256'] = sha(candidate/'report.json')
    # Independently reconstruct the seven exact matrices and expected optima.
    controls = observed['controls']['cases']; assert len(controls) == 7
    control_audits = []
    specs = [(1., [1., .2, .01], [.2, -.3, .4], [0., 0., 0.]),
        (1., [1., .2, .01], [2., -3., .4], [0., 0., 0.]),
        (1., [1., .2, .01], [0., 0., 0.], [0., 0., 0.]),
        (1., [1., .2, 0.], [.2, -.3, 0.], [0., 0., 0.]),
        (2**-16, [1., .2, .01], [2., -3., .4], [0., 0., 0.]),
        (1., [1., .2, .01], [0., 0., 0.], [1., 1., 1.])]
    for control, (radius, diagonal, target, initial) in zip(controls[:6], specs):
        diagonal = np.array(diagonal); gram = np.diag(diagonal); weighted = np.diag(np.sqrt(diagonal))
        target = radius*np.array(target); initial = radius*np.array(initial)
        rows = np.r_[np.eye(3), -np.eye(3)]; bounds = np.full(6, radius)
        result = inspect_path(gram, -gram@target, weighted, weighted@target, rows, bounds, initial, control['path'])
        final = np.array(control['path']['history'][-1]['primal_solution'])
        assert abs((final-np.clip(target, -radius, radius))[diagonal > 0]).max()/radius <= 1e-6
        control_audits.append(dict(id=control['id'], **result))
    rows = np.array([[1., 0.], [0., 1.], [1., 1.], [-1., 0.], [0., -1.]])
    bounds = np.array([3., 3., 2., 3., 3.]); g = np.array([-3., -2.])
    control_audits.append(dict(id='coupled', **inspect_path(np.eye(2), g, np.eye(2), -g, rows, bounds, np.zeros(2), controls[6]['path'])))
    r['controls'] = control_audits
    parent = args.workspace/'references/analysis/unit_box_qp_v1/fit1'
    assert observed['parent_report_sha256'] == sha(parent/'report.json') and observed['parent_fit_sha256'] == sha(parent/'fit.json')
    fitted = load(parent/'fit.json'); inputs = np.load(parent/'input.npz')
    time, audio, initial = (inputs[k] for k in ('time', 'audio', 'initial_parameters'))
    plan, settings = load(parent/'effective_plan.json'), load(parent/'effective_settings.json')
    assert settings == load(candidate/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, []); model.original.aperture = OrthogonalBand(len(time), plan)
    outer, amplitude = model.unpack(initial); scales = np.array(fitted['scales'])
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    saved_rows = {item['iteration']: item for item in observed['replays']}
    for row in fitted['history']:
        if row['iteration'] in saved_rows:
            folder = candidate/('step'+str(row['iteration'])); saved = np.load(folder/'input.npz')
            prediction, derivative = model.prediction(outer, amplitude, True)
            design = np.column_stack((derivative, model.design(outer)))*scales[None, :]
            gram, g, weighted, errors, v, roundoff = geometry(prediction-target, design, row['stage_scale'])
            rhs = -np.sqrt(np.r_[v, v])*(prediction-target)
            system = linear_system(Region(model, outer, amplitude, scales, row['radius'], settings))
            matrix, lower, upper = system; dense = matrix.toarray()
            for key, expected in dict(gram=gram, gradient=g, weighted=weighted, rhs=rhs, matrix=dense, lower=lower, upper=upper).items():
                assert np.array_equal(saved[key], expected), key
            high, low = np.flatnonzero(np.isfinite(upper)), np.flatnonzero(np.isfinite(lower))
            # Original CSC.toarray is F-contiguous. Its BLAS dot order is part
            # of bitwise execution replay; audit1 used C-order and failed.
            # Scalar final KKT and full-path forward bounds remain independent.
            rows = np.asfortranarray(np.r_[dense[high], -dense[low]])
            bounds = np.r_[upper[high], -lower[low]]
            q = load(folder/'new_QP.json'); old = load(folder/'old_failed_QP.json'); assert old == row['qp']
            coarse = old['coarse_attempt']; assert np.array_equal(saved['initial'], coarse['primal_solution'])
            assert saved_rows[row['iteration']]['input_sha256'] == sha(folder/'input.npz')
            assert saved_rows[row['iteration']]['new_QP_sha256'] == sha(folder/'new_QP.json')
            checked = inspect_path(gram, g, weighted, rhs, rows, bounds, saved['initial'], q['active_set_polish'])
            assert checked['success'] == q['success'] == saved_rows[row['iteration']]['success']
            r['replays'].append(dict(iteration=row['iteration'], **checked, geometry_errors=errors, factor_roundoff=roundoff))
        if row['accepted']:
            outer, amplitude = np.array(row['candidate_outer']), np.array(row['candidate_absolute_amplitudes'])
    assert [row['iteration'] for row in r['replays']] == [5, 11, 12]
    r.update(result='seven_controls_and_all57_blocking_iterates_independently_rebuilt',
        total_saved_iterates=sum(row['iterations'] for row in r['replays']),
        certified_QPs=sum(row['success'] for row in r['replays']),
        failed_QPs=[row['iteration'] for row in r['replays'] if not row['success']],
        all_paths_feasible=True, new_nonlinear_fit_permitted=False, original_dense_started=False,
        original_factor_relative_gate_failed_steps=[row['iteration'] for row in r['replays'] if not row['factor_roundoff']['original_gate1e12_passed']],
        supplemental_forward_bounds_passed=all(row['factor_roundoff']['component_bound_passed'] for row in r['replays']),
        limits=['Feasible path verified, but two final original KKT failures retained; no new nonlinear trajectory or real DNA.',
            'Do not add iterations or choose a truth-guided prefix; inspect the saved coarse primal-dual precision and observed convergence.'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(args.out/'report.json', r)
print(json.dumps({k:r[k] for k in ('result', 'total_saved_iterates', 'certified_QPs', 'failed_QPs')}), flush=True)
