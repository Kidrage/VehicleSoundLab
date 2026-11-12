"""Independent explicit/analytic checks, including contact addition and removal."""
import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
from joint_trust_v1.checks import controls as joint_controls
from joint_trust_v1.osqp_backend import linear_system
from .backend import inequalities
from .active_set import polish
from .sqrt_checks import controls as sqrt_controls


def controls(base, variant, settings):
    result = sqrt_controls(base, variant, settings)
    def solve_control(gram, gradient, region, config):
        root = la.cholesky(gram, lower=False)
        rhs = la.solve_triangular(root.T, -gradient, lower=True)
        rows, bounds, _, _ = inequalities(*linear_system(region))
        step, _, evidence = polish(gram, gradient, root, rhs, rows, bounds, np.zeros(len(gradient)), config)
        return step, evidence
    result['forced_active_explicit_polytope'] = joint_controls(base, variant, settings, qp_solver=solve_control)
    evidence_rows = []
    for label, diagonal, target, initial in (
        ('interior', [1., .2, .01], [.2, -.3, .4], [0., 0., 0.]),
        ('add_contacts', [1., .2, .01], [2., -3., .4], [0., 0., 0.]),
        ('drop_wrong_contact', [1., .2, .01], [-.2, -.3, .4], [1., 0., 0.]),
        ('zero_gradient', [1., .2, .01], [0., 0., 0.], [0., 0., 0.]),
        ('singular_PSD', [1., .2, 0.], [.2, -.3, 0.], [0., 0., 0.])):
        root = np.diag(np.sqrt(diagonal))
        gram = np.diag(diagonal)
        gradient = -gram@target
        rhs = root@target
        rows = sp.csc_matrix(np.r_[np.eye(3), -np.eye(3)])
        bounds = np.ones(6)
        actual, z, evidence = polish(gram, gradient, root, rhs, rows, bounds, np.asarray(initial), settings)
        assert evidence['success']
        identified = np.asarray(diagonal) > 0
        error = float(abs(actual[identified]-np.clip(target, -1, 1)[identified]).max())
        assert error < 1e-6
        actions = [row['action'] for row in evidence['history']]
        if label == 'add_contacts':
            assert actions.count('add_violated') == 2
        if label == 'drop_wrong_contact':
            assert actions.count('drop_negative_dual') == 1
        evidence_rows.append(dict(id=label, known_solution_error=error, evidence=evidence))
    result['active_set_analytic'] = evidence_rows
    return result
