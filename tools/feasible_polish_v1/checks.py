"""Analytic controls for blocking, dropping and original KKT units."""
import numpy as np
import scipy.sparse as sp
from interior_qp_v1.backend import inequalities
from unit_box_qp_v1.solver import metrics, certified
from .active_set import polish


def controls(settings):
    cases = [('interior', 1., [1., .2, .01], [.2, -.3, .4], [0., 0., 0.]),
        ('strict_active', 1., [1., .2, .01], [2., -3., .4], [0., 0., 0.]),
        ('zero', 1., [1., .2, .01], [0., 0., 0.], [0., 0., 0.]),
        ('singular', 1., [1., .2, 0.], [.2, -.3, 0.], [0., 0., 0.]),
        ('small_trust', 2**-16, [1., .2, .01], [2., -3., .4], [0., 0., 0.]),
        ('drop_faces', 1., [1., .2, .01], [0., 0., 0.], [1., 1., 1.])]
    results = []
    for label, radius, diagonal, target, initial in cases:
        diagonal = np.array(diagonal)
        target, initial = np.array(target)*radius, np.array(initial)*radius
        gram = np.diag(diagonal); weighted = np.diag(np.sqrt(diagonal))
        gradient, rhs = -gram@target, weighted@target
        matrix = sp.eye(3, format='csc'); lower = np.full(3, -radius); upper = -lower
        rows, bounds, _, _ = inequalities(matrix, lower, upper)
        x, z, details = polish(gram, gradient, weighted, rhs, rows, bounds, initial, settings)
        scale = float(abs(gradient).max()) or max(float(abs(gram).max()), 1.)
        y, q = metrics(gram, gradient, matrix, lower, upper, x, z, scale)
        expected = np.clip(target, lower, upper)
        identified = diagonal > 0
        error = float(abs((x[identified]-expected[identified])/radius).max())
        assert details['success'] and certified(q, settings) and error <= 1e-6, (label, error, q)
        results.append(dict(id=label, identified_unit_error=error, certificate=q, path=details))
    matrix = sp.csc_matrix([[1., 0.], [0., 1.], [1., 1.]])
    lower, upper = np.array([-3., -3., -np.inf]), np.array([3., 3., 2.])
    rows, bounds, _, _ = inequalities(matrix, lower, upper)
    g = np.array([-3., -2.])
    x, z, details = polish(np.eye(2), g, np.eye(2), -g, rows, bounds, np.zeros(2), settings)
    _, q = metrics(np.eye(2), g, matrix, lower, upper, x, z, 3.)
    error = float(abs(x-np.array([1.5, .5])).max())
    assert details['success'] and certified(q, settings) and error <= 1e-6
    results.append(dict(id='coupled', identified_unit_error=error, certificate=q, path=details))
    return dict(passed=True, cases=results, sweep=False)
