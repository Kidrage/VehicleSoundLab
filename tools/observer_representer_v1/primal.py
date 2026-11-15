"""Penalty-whitened Krylov range retains the exact representer, without dual recovery."""
import numpy as np
from scipy.sparse.linalg import LinearOperator, lsmr
from observer_inverse_v1.fit import real_vector, complex_array
from observer_frequency_v1.optimality import bound
from .dual import ObservationDual, representer_certificate


class PenaltyPrimal(LinearOperator):
    def __init__(self, system):
        self.system = system
        self.dual = ObservationDual(system)
        self.prior = self.dual.prior
        super().__init__(dtype=np.dtype(float), shape=(system.ysize+system.nsize, system.nsize))

    def _matvec(self, z):
        return np.r_[(self.system@self.prior.apply(z))[:self.system.ysize], z]

    def _rmatvec(self, v):
        return self.prior.transpose(self.dual.data_adjoint(v[:self.system.ysize]))+v[self.system.ysize:]


def infer(system, audio, maxiter=4000):
    primal = PenaltyPrimal(system)
    data = system.rhs(audio)[:system.ysize]
    result = lsmr(primal, np.r_[data, np.zeros(system.nsize)], atol=1e-11, btol=1e-11,
        conlim=1e12, maxiter=maxiter)
    x = primal.prior.apply(result[0])
    nodes = complex_array(x, system.nshape)*system.scale[None]
    residual = system@x-system.rhs(audio)
    u = -residual[:system.ysize]
    gradient = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(system.rhs(audio))), 1e-24))
    info = dict(stop=int(result[1]), iterations=int(result[2]), relative_stationarity=gradient,
        converged=bool(result[1] in (1, 2, 4, 5) and gradient < 2e-7), objective=float(residual@residual),
        atol=1e-11, btol=1e-11, conlim=1e12, maxiter=maxiter,
        estimated_penalty_whitened_condition=float(result[6]), same_original_objective=True,
        zero_initial_Krylov_range_representer_in_exact_arithmetic=True,
        no_diagonal_post_whitening_or_dual_reconstruction=True)
    return nodes, u, info, bound(system, audio, nodes), representer_certificate(system, audio, nodes, u)
