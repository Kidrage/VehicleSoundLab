"""Full raw-sample box/trust QP with the existing original-tolerance certificates."""
import numpy as np
import scipy.sparse as sp
from interior_qp_v1.square_root import solve_factorized
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish
from bounded_envelope_pair_v1.certificate import certify


def solve(design, rhs, lower, upper, settings):
    matrix = sp.eye(design.shape[1], format='csc')
    gram, gradient = design.T@design, -design.T@rhs
    factor = np.linalg.qr(design, mode='r')
    step, qp = solve_factorized(gram, gradient, matrix, lower, upper, settings, factor)
    coarse = certify(qp, design, rhs, matrix, lower, upper, settings)
    if coarse['success']:
        qp['primal_polish_attempted'] = False
    else:
        rows, bounds, high, low = inequalities(matrix, lower, upper)
        step, z, evidence = polish(gram, gradient, design, rhs, rows, bounds, step, settings)
        y = np.zeros(matrix.shape[0])
        y[high] += z[:len(high)]
        y[low] -= z[len(high):]
        qp = dict(primal_solution=step.tolist(), dual_solution=y.tolist(), inequality_dual=z.tolist(),
            objective_scale=qp['objective_scale'], objective=float(.5*step@gram@step+gradient@step),
            status='OriginalActiveSetCertificate' if evidence['success'] else 'FiniteActiveSetUncertified',
            primal_polish_attempted=True, polish=evidence, coarse_attempt=qp, coarse_certificate=coarse)
    final = certify(qp, design, rhs, matrix, lower, upper, settings)
    return step, dict(qp=qp, certificate=final, coarse_certificate=coarse,
        full_columns=int(design.shape[1]), ridge_added=False, cutoff_added=False)
