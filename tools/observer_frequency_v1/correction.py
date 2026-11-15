"""Saved-solution correction with the qualified within-order right map.

Only the coordinates used by LSMR change. All rows of the original weighted
complete-frame objective, including D2 and ridge rows, remain in the residual.
"""
import numpy as np
from scipy.sparse.linalg import LinearOperator, lsmr
from observer_inverse_v1.fit import real_vector, complex_array
from .block_right import OrderBlockRight


def correct(system, audio, initial_nodes, maxiter=4000):
    if initial_nodes.shape != system.nshape:
        raise ValueError('Saved node shape mismatch')
    if not np.isfinite(initial_nodes).all():
        raise ValueError('Nonfinite saved nodes')
    b = system.rhs(audio)
    x0 = real_vector(initial_nodes/system.scale[None])
    residual0 = b-system@x0
    denominator = max(np.linalg.norm(system.rmatvec(b)), 1e-24)
    initial_objective = float(residual0@residual0)
    initial_stationarity = float(np.linalg.norm(system.rmatvec(residual0))/denominator)
    right = OrderBlockRight(system)
    op = LinearOperator(system.shape,
        matvec=lambda u: system@right.apply(u),
        rmatvec=lambda y: right.transpose(system.rmatvec(y)), dtype=float)
    result = lsmr(op, residual0, atol=1e-13, btol=1e-13,
                  conlim=1e12, maxiter=maxiter)
    x = x0+right.apply(result[0])
    residual = system@x-b
    objective = float(residual@residual)
    stationarity = float(np.linalg.norm(system.rmatvec(residual))/denominator)
    if objective > initial_objective*(1+2e-10)+1e-20:
        raise ArithmeticError('Correction increased the unchanged objective')
    info = dict(stop=int(result[1]), iterations=int(result[2]),
        initial_objective=initial_objective, objective=objective,
        initial_relative_stationarity=initial_stationarity,
        relative_stationarity=stationarity,
        converged=bool(result[1] in (1, 2, 4, 5) and stationarity < 2e-7),
        estimated_preconditioned_condition=float(result[6]),
        alpha=system.alpha, beta=system.beta, atol=1e-13, btol=1e-13,
        correction_solve=True, same_weighted_objective=True,
        changed_preconditioner='within-order full real/imag time block',
        equivalent_saved_right_map=False, source_time_law_changed=False,
        not_physical_or_stochastic_source=True)
    return complex_array(x, system.nshape)*system.scale[None], info, right
