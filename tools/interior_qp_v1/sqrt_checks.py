"""Explicit-polytope/SLSQP controls plus analytic PSD lifted problems."""
import numpy as np
import scipy.sparse as sp
from joint_trust_v1.checks import controls as original_controls
from .square_root import solve_control, solve_factorized


def controls(base, variant, settings):
    result = original_controls(base, variant, settings, qp_solver=solve_control)
    rows = []
    for label, diagonal, target in (
        ('interior', [1., .2, .01], [.2, -.3, .4]),
        ('active', [1., .2, .01], [2., -3., .4]),
        ('zero_gradient', [1., .2, .01], [0., 0., 0.]),
        ('singular_positive_semidefinite', [1., .2, 0.], [.2, -.3, 0.])):
        gram = np.diag(diagonal)
        gradient = -gram@target
        lower, upper = np.full(3, -1.), np.full(3, 1.)
        root = np.diag(np.sqrt(diagonal))
        actual, certificate = solve_factorized(gram, gradient, sp.eye(3, format='csc'), lower, upper, settings, root)
        expected = np.clip(target, lower, upper)
        assert certificate['success']
        identified = np.asarray(diagonal) > 0
        error = float(abs(actual[identified]-expected[identified]).max())
        assert error < 1e-6
        rows.append(dict(id=label, known_identified_solution_maximum_error=error, certificate=certificate))
    result['analytic_quadratics'] = rows
    result['certificate_uses_original_Gram'] = True
    return result
