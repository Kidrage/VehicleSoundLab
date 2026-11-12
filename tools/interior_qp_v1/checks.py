"""Independent nonzero/active polytope and known diagonal quadratic controls."""
import numpy as np
import scipy.sparse as sp
from joint_trust_v1.checks import controls as original_controls
from .backend import solve, solve_polytope


def controls(base, variant, settings):
    result = original_controls(base, variant, settings, qp_solver=solve)
    rows = []
    for label, diagonal, target in (
        ('interior', [1., .2, .01], [.2, -.3, .4]),
        ('active', [1., .2, .01], [2., -3., .4]),
        ('zero_gradient', [1., .2, .01], [0., 0., 0.]),
        ('singular_positive_semidefinite', [1., .2, 0.], [.2, -.3, 0.])):
        gram = np.diag(diagonal)
        gradient = -gram@target
        lower, upper = np.full(3, -1.), np.full(3, 1.)
        actual, certificate = solve_polytope(gram, gradient, sp.eye(3, format='csc'), lower, upper, settings)
        expected = np.clip(target, lower, upper)
        assert certificate['success']
        # A singular direction is nonunique: compare its objective/feasibility,
        # and the uniquely determined coordinates, rather than its arbitrary x.
        identified = np.asarray(diagonal) > 0
        error = float(abs(actual[identified]-expected[identified]).max())
        assert error < 1e-6
        rows.append(dict(id=label, known_identified_solution_maximum_error=error, certificate=certificate))
    result['analytic_quadratics'] = rows
    result['native_success_is_not_sole_certificate'] = True
    return result
