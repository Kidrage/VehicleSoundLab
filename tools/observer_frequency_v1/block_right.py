"""Data-aware within-order preconditioning; the weighted objective stays exact."""
import numpy as np
from scipy import linalg
from observer_inverse_v1.fit import real_vector, complex_array


class OrderBlockRight:
    """Whiten each full real/imag time block, using its carrier weight approximation.

    Off-order and frequency-sideband couplings remain in the exact forward/adjoint.
    No source coordinate, harmonic, temporal node or regularization is removed.
    """
    def __init__(self, system):
        s = system.synthesis
        self.shape = s.shape
        M, H, C = self.shape
        n = np.arange(s.frames)
        basis = np.array([np.interp(n, s.positions, row) for row in np.eye(M)])
        mass = np.zeros((M, M))
        moment = np.zeros((H, M, M), complex)
        for i in range(M):
            for j in range(i, min(M, i+2)):
                product = basis[i]*basis[j]
                bins = np.bincount(n % 1024, weights=product, minlength=1024)
                mass[i, j] = mass[j, i] = bins.sum()
                value = np.fft.fft(bins)[(2*s.orders) % 1024].conj()
                moment[:, i, j] = moment[:, j, i] = value
        D = system.D.toarray()
        penalty = system.alpha*D.T@D+system.beta*np.eye(M)
        regularizer = linalg.block_diag(penalty, penalty)
        factors = []
        for h, order in enumerate(s.orders):
            cosine = .5*(mass+moment[h].real)
            sine = .5*(mass-moment[h].real)
            cross = -.5*moment[h].imag
            data = np.block([[cosine, cross], [cross, sine]])
            gain = (system.scale[h, 0]*system.metric.weights[4*order])**2
            K = regularizer+gain*data
            factors.append(linalg.solve_triangular(np.linalg.cholesky(K).T, np.eye(2*M), lower=False))
        self.matrix = np.array(factors)

    def _map(self, vector, transpose):
        u = complex_array(vector, self.shape)
        M = self.shape[0]
        pair = np.concatenate((u.real, u.imag), axis=0).transpose(1, 0, 2)
        matrix = self.matrix.transpose(0, 2, 1) if transpose else self.matrix
        result = (matrix@pair).transpose(1, 0, 2)
        return real_vector(result[:M]+1j*result[M:])

    def apply(self, vector): return self._map(vector, False)

    def transpose(self, vector): return self._map(vector, True)
