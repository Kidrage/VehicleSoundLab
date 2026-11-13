"""One finite QR-lifted least-squares QP on every original amplitude column."""
import numpy as np
from interior_qp_v1.square_root import solve_factorized
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish
from .constraints import ranged
from .certificate import certify


def fit(design, target, initial, bound, caps, settings):
    matrix, lower, upper = ranged(initial.shape, bound, caps)
    center = initial.ravel()
    lower, upper = lower-matrix@center, upper-matrix@center
    rhs = target-design@center
    gram = design.T@design
    gradient = -(design.T@rhs)
    factor = np.linalg.qr(design, mode='r')
    step, qp = solve_factorized(gram, gradient, matrix, lower, upper, settings, factor)
    first_certificate = certify(qp, design, rhs, matrix, lower, upper, settings)
    if first_certificate['success']:
        qp['primal_polish_attempted'] = False
    else:
        rows, bounds, high, low = inequalities(matrix, lower, upper)
        step, z, evidence = polish(gram, gradient, design, rhs, rows, bounds, step, settings)
        y = np.zeros(matrix.shape[0])
        y[high] += z[:len(high)]
        y[low] -= z[len(high):]
        scale = qp['objective_scale']
        final = dict(primal_solution=step.tolist(), dual_solution=y.tolist(), inequality_dual=z.tolist(),
            objective_scale=scale, objective=float(.5*step@gram@step+gradient@step),
            status='OriginalActiveSetCertificate' if evidence['success'] else 'FiniteActiveSetUncertified',
            primal_polish_attempted=True, polish=evidence, coarse_attempt=qp,
            coarse_certificate=first_certificate)
        qp = final
    certificate = certify(qp, design, rhs, matrix, lower, upper, settings)
    values = (center+step).reshape(initial.shape)
    return values, dict(qp=qp, certificate=certificate, coarse_certificate=first_certificate,
        amplitude_columns=design.shape[1], observation_rows=design.shape[0],
        objective='raw_sample_squared_difference', ridge_added=False,
        nonlinear_estimator_run=False, full_source_columns_retained=True)
