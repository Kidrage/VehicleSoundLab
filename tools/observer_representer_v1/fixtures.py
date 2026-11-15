"""Finite algebra fixtures; explicitly not the4096-point source observation metric."""
import numpy as np
from scipy import fft, linalg, sparse
from scipy.sparse.linalg import LinearOperator
from observer_inverse_v1.fit import real_vector


class DenseFixture(LinearOperator):
    def __init__(self, channels, weak, silent_right=False):
        N, M, H = 33, 9, 3
        self.nshape = (M, H, channels)
        self.nsize = 2*M*H*channels
        self.ysize = N*channels
        self.scale = np.array([[1.], [.01], [weak]])
        self.alpha, self.beta = .001, .000001
        self.positions, self.orders = np.arange(M)*4, np.array([7, 8, 211])
        D = np.zeros((M-2, M))
        for j in range(M-2):
            D[j, j:j+3] = [1., -2., 1.]
        self.D = sparse.csr_matrix(D)
        size = self.nsize//2
        self.Phi = np.zeros((N*channels, self.nsize))
        for j in range(M):
            hat = np.interp(np.arange(N), self.positions, np.eye(M)[j])
            for h, order in enumerate(self.orders):
                angle = 2*np.pi*((np.arange(N)*order) % 1024)/1024
                for c in range(channels):
                    k = (j*H+h)*channels+c
                    self.Phi[c::channels, k] = self.scale[h, 0]*hat*np.cos(angle)
                    self.Phi[c::channels, size+k] = -self.scale[h, 0]*hat*np.sin(angle)
        dct = fft.dct(np.eye(N), type=2, axis=0, norm='ortho')
        weights = np.geomspace(1., 100., N)
        single = np.eye(N)+dct.T@(weights[:, None]**2*dct)
        self.wave_metric = np.kron(single, np.eye(channels))
        self.Hroot = np.linalg.cholesky(self.wave_metric).T
        self.B = self.Hroot@self.Phi
        k = self.alpha*D.T@D+self.beta*np.eye(M)
        self.R = linalg.block_diag(np.kron(k, np.eye(H*channels)), np.kron(k, np.eye(H*channels)))
        reg = np.sqrt(self.alpha)*linalg.block_diag(np.kron(D, np.eye(H*channels)), np.kron(D, np.eye(H*channels)))
        self.A = np.vstack((self.B, reg, np.sqrt(self.beta)*np.eye(self.nsize)))
        q = np.exp(1j*(np.arange(H)[None, :, None]*.31+np.arange(channels)[None, None, :]*.7))
        q = np.broadcast_to(q, self.nshape).copy()
        q *= 1+.2*np.sin(np.arange(M)[:, None, None]*.8+np.arange(H)[None, :, None]*.5)
        if silent_right:
            q[:, :, 1] = 0
        self.truth = q
        self.audio = (self.Phi@real_vector(q)).reshape(N, channels)
        super().__init__(dtype=np.dtype(float), shape=self.A.shape)

    def _matvec(self, x):
        return self.A@x

    def _rmatvec(self, y):
        return self.A.T@y

    def rhs(self, audio):
        return np.r_[self.Hroot@audio.ravel(), np.zeros(self.shape[0]-self.ysize)]
