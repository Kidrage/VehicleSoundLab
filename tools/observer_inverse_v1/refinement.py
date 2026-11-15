"""Solve corrections to saved iterates without changing the inference objective."""
import numpy as np
from scipy.sparse.linalg import LinearOperator, lsmr
from .fit import real_vector, complex_array


class SavedRightMap:
    """The original, invertible right map; no new whitening or source refit."""
    def __init__(self, shape, time, real_scale, imag_scale):
        self.shape = tuple(shape)
        self.time = np.asarray(time, float)
        self.real_scale = np.asarray(real_scale, float)
        self.imag_scale = np.asarray(imag_scale, float)
        m, h, _ = self.shape
        if self.time.shape != (m, m) or any(x.shape != (m, h, 1) for x in (self.real_scale, self.imag_scale)):
            raise ValueError('Saved right-map shape mismatch')
        if any(not np.isfinite(x).all() for x in (self.time, self.real_scale, self.imag_scale)):
            raise ValueError('Nonfinite right map')
        if min(self.real_scale.min(), self.imag_scale.min()) <= 0 or np.linalg.matrix_rank(self.time) != m:
            raise ValueError('Noninvertible right map')

    def apply(self, vector):
        u = complex_array(vector, self.shape)
        mixed = u.real*self.real_scale + 1j*u.imag*self.imag_scale
        return real_vector((self.time@mixed.reshape(len(u), -1)).reshape(self.shape))

    def transpose(self, vector):
        g = complex_array(vector, self.shape)
        mixed = (self.time.T@g.reshape(len(g), -1)).reshape(self.shape)
        return real_vector(mixed.real*self.real_scale + 1j*mixed.imag*self.imag_scale)


def refine(system, right, target, initial_nodes, maxiter=4000):
    """Minimize ||A(x0+Pdu)-b||, including the unchanged D2 and ridge rows."""
    if initial_nodes.shape != system.nshape:
        raise ValueError('Initial node shape mismatch')
    b = system.rhs(target)
    x0 = real_vector(initial_nodes/system.scale[None])
    residual0 = b-system@x0
    initial_gradient = system.rmatvec(b)
    denominator = max(np.linalg.norm(initial_gradient), 1e-24)
    start_stationarity = float(np.linalg.norm(system.rmatvec(residual0))/denominator)
    operator = LinearOperator(system.shape,
        matvec=lambda u: system@right.apply(u),
        rmatvec=lambda v: right.transpose(system.rmatvec(v)), dtype=float)
    result = lsmr(operator, residual0, atol=1e-13, btol=1e-13,
                  conlim=1e12, maxiter=maxiter)
    x = x0+right.apply(result[0])
    residual = system@x-b
    stationarity = float(np.linalg.norm(system.rmatvec(residual))/denominator)
    objective = float(residual@residual)
    if objective > float(residual0@residual0)*(1+2e-10)+1e-20:
        raise ArithmeticError('Correction increased the original objective')
    info = dict(stop=int(result[1]), iterations=int(result[2]),
        residual_norm=float(result[3]), normal_residual_norm=float(result[4]),
        estimated_preconditioned_operator_norm=float(result[5]),
        estimated_preconditioned_condition=float(result[6]),
        solution_norm=float(np.linalg.norm(x)),
        objective=objective, relative_stationarity=stationarity,
        initial_objective=float(residual0@residual0),
        initial_relative_stationarity=start_stationarity,
        alpha=system.alpha, beta=system.beta,
        converged=bool(result[1] in (1, 2, 4, 5) and stationarity < 2e-7),
        equivalent_saved_right_map=True, correction_solve=True,
        preconditioned_atol=1e-13, preconditioned_btol=1e-13,
        not_unique_physical_trajectory=True)
    return complex_array(x, system.nshape)*system.scale[None], info
