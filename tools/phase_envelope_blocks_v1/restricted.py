"""Exact coordinate restriction of the original convex polytope and QR QP."""
import numpy as np
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.square_root import solve_factorized
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish


def restrict(matrix, lower, upper, active):
    active = np.asarray(active)
    if (active.ndim != 1 or not len(active) or active.dtype.kind not in 'iu'
            or len(np.unique(active)) != len(active) or active.min() < 0 or active.max() >= matrix.shape[1]):
        raise ValueError('Nonempty unique valid integer coordinate indices required')
    reduced = matrix[:, active].tocsc(copy=True)
    reduced.eliminate_zeros()
    keep = np.flatnonzero(np.asarray(reduced.getnnz(axis=1)).ravel() != 0)
    removed = np.flatnonzero(np.asarray(reduced.getnnz(axis=1)).ravel() == 0)
    if np.any(lower[removed] > 0) or np.any(upper[removed] < 0):
        raise ValueError('Frozen coordinates violate an original zero-row constraint')
    return reduced[keep].tocsc(), lower[keep], upper[keep], keep


def solve_reduced(gram, gradient, weighted, rhs, matrix, lower, upper, settings):
    """Same original solver/fallback; certificate applies to supplied coordinates."""
    assert np.linalg.norm(weighted.T@weighted-gram) <= 1e-12*max(1., np.linalg.norm(gram))
    assert np.linalg.norm(weighted.T@rhs+gradient) <= 1e-12*max(1., np.linalg.norm(gradient))
    step, coarse = solve_factorized(gram, gradient, matrix, lower, upper, settings,
        np.linalg.qr(weighted, mode='r'))
    if coarse['success']:
        coarse['active_set_polish'] = dict(attempted=False)
        return step, coarse
    rows, bounds, high, low = inequalities(matrix, lower, upper)
    step, z, evidence = polish(gram, gradient, weighted, rhs, rows, bounds, step, settings)
    y = np.zeros(matrix.shape[0]); y[high] += z[:len(high)]; y[low] -= z[len(high):]
    scale = coarse['objective_scale']; normal = (gram+gram.T)/(2*scale); value = matrix@step
    primal = float(max(0., np.max(lower-value), np.max(value-upper)))
    dual = float(abs(normal@step+gradient/scale+matrix.T@y).max())
    sign = float(max(0., -z.min())); comp = float(abs(z*(bounds-rows@step)).max())
    success = bool(evidence['success'] and primal <= settings['maximum_primal_violation']
        and dual <= settings['maximum_normalized_stationarity'] and sign <= settings['maximum_primal_violation']
        and comp <= settings['maximum_complementarity'])
    return step, dict(success=success, status='SolvedActiveSet' if success else 'ActiveSetUncertified',
        status_value=1 if success else 0, native_success=success, external_native_status=coarse['status'],
        termination='independent_original_KKT_certificate', iterations=evidence['iterations'], solver_version=coarse['solver_version'],
        normalized_dual_stationarity=dual, constraint_violation=primal, inequality_dual_sign_violation=sign,
        maximum_complementarity=comp, normalized_duality_gap=float(z@(bounds-rows@step)),
        original_objective_dual_stationarity=dual*scale, objective_scale=scale,
        objective=float(.5*step@gram@step+gradient@step), external_hessian_regularization=False,
        linear_constraints=matrix.shape[0], inequality_constraints=len(bounds), primal_solution=step.tolist(),
        dual_solution=y.tolist(), inequality_dual=z.tolist(), coarse_attempt=coarse,
        active_set_polish=dict(attempted=True, **evidence), factor_source='restricted_exact_complex_block_Hessian',
        truth_used=False, heldout_used=False)


def solve(gram, gradient, weighted, rhs, region, settings, active):
    matrix, lower, upper = linear_system(region)
    reduced, lo, hi, keep = restrict(matrix, lower, upper, active)
    local, evidence = solve_reduced(gram[np.ix_(active, active)], gradient[active], weighted[:, active],
        rhs, reduced, lo, hi, settings)
    full = np.zeros(len(gradient)); full[active] = local
    inactive = np.setdiff1d(np.arange(len(full)), active)
    full_dual = np.zeros(len(lower)); full_dual[keep] = evidence['dual_solution']
    stationarity = (gram@full+gradient)/evidence['objective_scale']+matrix.T@full_dual
    evidence.update(certificate_scope='active_coordinates_only_other_coordinates_fixed_zero',
        active_coordinates=active.tolist(), retained_constraint_rows=keep.tolist(), full_dimension=len(full),
        inactive_stationarity_diagnostic=float(abs(stationarity[inactive]).max()) if len(inactive) else 0.)
    return full, evidence
