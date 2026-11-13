"""Fixed analytic subspace controls, independently certified before known fitting."""
import ast
import numpy as np
import scipy.sparse as sp
from interior_qp_v1.backend import inequalities
from .restricted import restrict, solve_reduced


def certificate_function(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'certificate')
    ns = dict(np=np, linear_system=lambda system: system, inequalities=inequalities)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), ns)
    return ns['certificate']


def analytic_error(step, expected, gram, gradient, system, qp):
    """Strong-convexity distance bound from a feasible primal/dual pair.

    A weakly active bound has zero exact multiplier: a tiny QP gap controls
    squared distance, not distance. The original arbitrary1e-7 coordinate
    assertion failed; retain that failure without changing solver gates.
    """
    matrix, lo, hi = system
    rows, bounds, high, low = inequalities(matrix, lo, hi)
    z = np.asarray(qp['inequality_dual'])
    assert np.min(z) >= 0 and np.min(bounds-rows@step) >= 0
    smallest = float(np.linalg.eigvalsh(gram).min()); assert smallest > 0
    residual = gram@step+gradient+qp['objective_scale']*(rows.T@z)
    gap_bound = float(qp['objective_scale']*(z@(bounds-rows@step))+.5*(residual@residual)/smallest)
    distance_bound = float(np.sqrt(2*max(0., gap_bound)/smallest))
    distance = float(np.linalg.norm(step-expected))
    rounding = 64*np.finfo(float).eps*max(1., float(np.linalg.norm(expected)))
    assert distance <= distance_bound+rounding
    return dict(distance=distance, distance_bound=distance_bound, duality_gap_bound=gap_bound,
        original_1e7_coordinate_assertion_passed=bool(abs(step-expected).max() < 1e-7),
        bound_passed=True)


def controls(settings, certificate_path):
    certificate = certificate_function(certificate_path)
    active = np.array([0, 2]); matrix = sp.eye(4, format='csc')
    lo = np.array([-.5, -1., -.25, -1.]); hi = -lo
    weighted = np.diag(np.sqrt([2., 3., 4., 5.])); gradient = np.array([-4., 7., 1., -6.])
    rhs = np.linalg.solve(weighted.T, -gradient); gram = weighted.T@weighted
    a, l, u, keep = restrict(matrix, lo, hi, active)
    step, qp = solve_reduced(gram[np.ix_(active, active)], gradient[active], weighted[:, active], rhs, a, l, u, settings)
    box = certificate(qp, gram[np.ix_(active, active)], gradient[active], (a, l, u), weighted[:, active])
    error = float(abs(step-np.array([.5, -.25])).max()); assert box['success']
    box_bound = analytic_error(step, np.array([.5, -.25]), gram[np.ix_(active, active)], gradient[active], (a, l, u), qp)
    assert np.array_equal(keep, active)
    # A coupled halfspace has exact optimum (1.5,.5), not coordinate clipping.
    matrix2 = sp.vstack((sp.eye(4, format='csc'), sp.csc_matrix([[1., 0., 1., 0.]])), format='csc')
    lo2 = np.r_[np.full(4, -3.), -np.inf]; hi2 = np.r_[np.full(4, 3.), 2.]
    g2 = np.array([-3., 4., -2., 5.]); w2 = np.eye(4); rhs2 = -g2
    a2, l2, u2, keep2 = restrict(matrix2, lo2, hi2, active)
    step2, qp2 = solve_reduced(np.eye(2), g2[active], w2[:, active], rhs2, a2, l2, u2, settings)
    coupled = certificate(qp2, np.eye(2), g2[active], (a2, l2, u2), w2[:, active])
    error2 = float(abs(step2-np.array([1.5, .5])).max()); assert coupled['success'] and error2 < 1e-7
    # Permuting the selected columns and lifting must preserve the same full solution.
    reverse = active[::-1]; ar, lr, ur, kr = restrict(matrix2, lo2, hi2, reverse)
    sr, qr = solve_reduced(np.eye(2), g2[reverse], w2[:, reverse], rhs2, ar, lr, ur, settings)
    permuted = certificate(qr, np.eye(2), g2[reverse], (ar, lr, ur), w2[:, reverse])
    full, fullr = np.zeros(4), np.zeros(4); full[active] = step2; fullr[reverse] = sr
    permutation_error = float(abs(full-fullr).max()); assert permuted['success'] and permutation_error < 1e-7
    zero, q0 = solve_reduced(np.eye(2), np.zeros(2), np.eye(2), np.zeros(2), sp.eye(2, format='csc'),
        np.full(2, -1.), np.full(2, 1.), settings)
    assert q0['success'] and abs(zero).max() < 1e-9
    # The old certificate's nonzero-gradient normalization is inapplicable here;
    # independently check zero case with its solver-defined finite Hessian scale.
    assert q0['objective_scale'] == 1. and q0['normalized_dual_stationarity'] <= 1e-8
    invalid = 0
    for bad in (np.array([], dtype=int), np.array([0, 0]), np.array([-1]), np.array([4]), np.array([.5])):
        try: restrict(matrix, lo, hi, bad)
        except ValueError: invalid += 1
        else: raise AssertionError('Invalid active coordinates accepted')
    bad_lo = lo.copy(); bad_lo[1] = .1
    try: restrict(matrix, bad_lo, hi, active)
    except ValueError: invalid += 1
    else: raise AssertionError('Infeasible frozen row silently removed')
    return dict(passed=True, diagonal_box_maximum_error=error, coupled_halfspace_maximum_error=error2,
        weakly_active_box_distance_bound=box_bound,
        permutation_lift_error=permutation_error, box_certificate=box, coupled_certificate=coupled,
        permutation_certificate=permuted, zero_gradient=True, invalid_cases_rejected=invalid,
        scope='Only active coordinates are certified; nonzero inactive gradients allowed')
