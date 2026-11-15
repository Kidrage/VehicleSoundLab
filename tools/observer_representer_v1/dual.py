"""Square-root observation representer for the unchanged regularized objective."""
import numpy as np
from scipy import linalg
from scipy.sparse.linalg import LinearOperator, lsmr
from observer_inverse_v1.fit import real_vector, complex_array
from observer_frequency_v1.optimality import bound


class PenaltyRoot:
    def __init__(self, system):
        self.shape = system.nshape
        D = system.D.toarray()
        self.R = system.alpha*D.T@D + system.beta*np.eye(len(D)+2)
        self.L = np.linalg.cholesky(self.R)

    def _solve(self, x, transpose):
        q = complex_array(x, self.shape)
        matrix = self.L if transpose else self.L.T
        out = linalg.solve_triangular(matrix, q.reshape(len(q), -1), lower=transpose)
        return real_vector(out.reshape(q.shape))

    def apply(self, x):
        return self._solve(x, False)

    def transpose(self, x):
        return self._solve(x, True)


class ObservationDual(LinearOperator):
    def __init__(self, system):
        self.system = system
        self.prior = PenaltyRoot(system)
        super().__init__(dtype=np.dtype(float), shape=(system.nsize+system.ysize, system.ysize))

    def data_adjoint(self, u):
        rows = np.zeros(self.system.shape[0])
        rows[:self.system.ysize] = u
        return self.system.rmatvec(rows)

    def _matvec(self, u):
        return np.r_[self.prior.transpose(self.data_adjoint(u)), u]

    def _rmatvec(self, v):
        q = self.prior.apply(v[:self.system.nsize])
        return (self.system@q)[:self.system.ysize] + v[self.system.nsize:]

    def restore(self, u):
        return self.prior.apply(self.prior.transpose(self.data_adjoint(u)))


def representer_certificate(system, audio, nodes, u):
    dual = ObservationDual(system)
    x = real_vector(nodes/system.scale[None])
    b = system.rhs(audio)[:system.ysize]
    e = (system@x)[:system.ysize]-b
    restored = dual.restore(u)
    q = complex_array(x, system.nshape)
    v = complex_array(restored, system.nshape)
    D = system.D.toarray()
    def penalty(z):
        d = D@z.reshape(len(z), -1)
        return float(system.alpha*np.sum(abs(d)**2)+system.beta*np.sum(abs(z)**2))
    primal = float(e@e)+penalty(q)
    lower = float(2*b@u-u@u)-penalty(v)
    gap = float((e+u)@(e+u))+penalty(q-v)
    if abs(primal-lower-gap) > 2e-8*max(1., primal, abs(lower)):
        raise ArithmeticError('Observation representer primal/dual identity failed')
    return dict(primal=primal, dual_lower_bound=lower, gap_upper_bound=gap,
        relative_gap_upper_bound=gap/max(primal, 1e-24),
        additional_gap_gate_passed=bool(gap <= 1e-6*primal+1e-10),
        relative_gate=1e-6, absolute_gate=1e-10,
        original_residual_gap_not_replaced=True, floating_point_not_interval_certificate=True)


def infer(system, audio, maxiter=4000):
    dual = ObservationDual(system)
    b = system.rhs(audio)[:system.ysize]
    result = lsmr(dual, np.r_[np.zeros(system.nsize), b], atol=1e-11, btol=1e-11,
        conlim=1e12, maxiter=maxiter)
    u = result[0]
    x = dual.restore(u)
    nodes = complex_array(x, system.nshape)*system.scale[None]
    residual = system@x-system.rhs(audio)
    gradient = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(system.rhs(audio))), 1e-24))
    info = dict(stop=int(result[1]), iterations=int(result[2]), relative_stationarity=gradient,
        converged=bool(result[1] in (1, 2, 4, 5) and gradient < 2e-7),
        objective=float(residual@residual), atol=1e-11, btol=1e-11, conlim=1e12,
        estimated_augmented_dual_condition=float(result[6]), maxiter=maxiter,
        same_original_objective=True, no_inner_iterative_inverse=True)
    return nodes, u, info, bound(system, audio, nodes), representer_certificate(system, audio, nodes, u)
