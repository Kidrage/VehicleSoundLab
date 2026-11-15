"""NEW weighted full-frame least squares with unchanged node/ridge/curvature sizes."""
import numpy as np
from scipy import linalg
from scipy.sparse.linalg import LinearOperator, lsmr
from observer_complete_v1.fit import CompleteSystem
from observer_inverse_v1.fit import real_vector, complex_array
from observer_inverse_v1.refinement import SavedRightMap


class WeightedSystem(CompleteSystem):
    def __init__(self, synthesis, scale, metric, alpha=1e-3, beta=1e-6):
        super().__init__(synthesis, scale, 1., alpha, beta)
        if (metric.frame.frames, metric.frame.channels) != (synthesis.frames, synthesis.channels):
            raise ValueError('Metric/synthesis dimensions differ')
        self.metric = metric
        self.yshape = metric.shape
        self.ysize = 2*int(np.prod(self.yshape))
        LinearOperator.__init__(self, dtype=np.dtype(float),
            shape=(self.ysize+self.dsize+self.nsize, self.nsize))

    def _matvec(self, x):
        q = complex_array(x, self.nshape)
        rows = self.metric.forward(self.synthesis.synthesize(q*self.scale[None]))
        d = (self.D@q.reshape(len(q), -1)).reshape(self.dshape)
        return np.r_[real_vector(rows), np.sqrt(self.alpha)*real_vector(d), np.sqrt(self.beta)*x]

    def _rmatvec(self, x):
        rows = complex_array(x[:self.ysize], self.yshape)
        d = complex_array(x[self.ysize:self.ysize+self.dsize], self.dshape)
        g = self.synthesis.adjoint(self.metric.adjoint(rows))*self.scale[None]
        g += np.sqrt(self.alpha)*(self.D.T@d.reshape(len(d), -1)).reshape(self.nshape)
        return real_vector(g)+np.sqrt(self.beta)*x[-self.nsize:]

    def rhs(self, audio):
        return np.r_[real_vector(self.metric.forward(audio)), np.zeros(self.dsize+self.nsize)]


class FrequencyRight(SavedRightMap):
    """Invertible time whitening with APPROXIMATE carrier-frequency column scaling.

    Sidebands see different weights; no exact unit-column-norm claim is made.
    The forward objective and its adjoint always use the complete weighted frame.
    """
    def __init__(self, system):
        s = system.synthesis
        D = system.D.toarray()
        K = system.alpha*D.T@D+system.beta*np.eye(len(s.positions))
        T = linalg.solve_triangular(np.linalg.cholesky(K).T, np.eye(len(s.positions)), lower=False)
        n = np.arange(s.frames)
        weight = system.metric.weights[4*s.orders]
        re, im = [], []
        for j in range(len(s.positions)):
            hat = np.interp(n, s.positions, T[:, j])
            bins = np.bincount(n % 1024, weights=hat**2, minlength=1024)
            twice = np.fft.fft(bins)[(2*s.orders) % 1024].real
            a = .5*(bins.sum()+twice)*(system.scale[:, 0]*weight)**2
            b = .5*(bins.sum()-twice)*(system.scale[:, 0]*weight)**2
            if min(a.min(), b.min()) < -1e-8:
                raise ArithmeticError('Negative approximate column norm')
            re.append(1/np.sqrt(1+np.maximum(a, 0)))
            im.append(1/np.sqrt(1+np.maximum(b, 0)))
        super().__init__(s.shape, T, np.array(re)[:, :, None], np.array(im)[:, :, None])


def infer(synthesis, audio, scale, metric, maxiter=4000):
    system = WeightedSystem(synthesis, scale, metric)
    right = FrequencyRight(system)
    op = LinearOperator(system.shape, matvec=lambda u: system@right.apply(u),
        rmatvec=lambda v: right.transpose(system.rmatvec(v)), dtype=float)
    b = system.rhs(audio)
    result = lsmr(op, b, atol=1e-11, btol=1e-11, conlim=1e12, maxiter=maxiter)
    x = right.apply(result[0])
    residual = system@x-b
    stationarity = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(b)), 1e-24))
    info = dict(stop=int(result[1]), iterations=int(result[2]), objective=float(residual@residual),
        relative_stationarity=stationarity,
        converged=bool(result[1] in (1, 2, 4, 5) and stationarity < 2e-7),
        alpha=system.alpha, beta=system.beta, atol=1e-11, btol=1e-11,
        estimated_preconditioned_condition=float(result[6]),
        new_weighted_complete_objective=True, approximate_carrier_column_preconditioner=True,
        not_physical_source_trajectory=True)
    return complex_array(x, synthesis.shape)*scale[None], info, right
