"""Canonical marginal noise decorrelation without changing raw samples or source equations."""
import numpy as np
from native_observation_v1.noise_geometry import sample_rows


class MarginalAperture:
    def __init__(self, aperture):
        self.base = aperture
        differences = aperture.bins[:, None]-aperture.bins[None, :]
        correlation = np.zeros(differences.shape)
        correlation[differences == 0] = 1.
        correlation[abs(differences) == 1] = -2/3
        correlation[abs(differences) == 2] = 1/6
        # R = D D^T exactly, with D the three-tap Hann second-difference factor.
        # SVD of D avoids squaring its condition number in the eigensolve.
        factor = np.zeros((len(aperture.bins), len(aperture.bins)+2))
        for index in range(len(aperture.bins)):
            factor[index, index:index+3] = np.array((1., -2., 1.))/np.sqrt(6.)
        if not np.array_equal(np.diff(aperture.bins), np.ones(len(aperture.bins)-1, dtype=int)):
            raise ValueError('Hann difference factor requires contiguous native bins')
        vectors, singular, _ = np.linalg.svd(factor, full_matrices=False)
        if singular.min() <= 0:
            raise ArithmeticError('The marginal covariance is not positive definite')
        self.correlation = correlation
        self.factor = factor
        self.eigenvalues = np.sort(singular**2)
        self.symmetric = (vectors/singular[None, :])@vectors.T
        self.real_noise_variance = 2*np.sum(aperture.window**2)/aperture.window.sum()**2
        self.frames = int(aperture.starts[-1]+aperture.size)

    def __getattr__(self, name):
        return getattr(self.base, name)

    def transform(self, values):
        vector = values.ndim == 1
        columns = 1 if vector else values.shape[1]
        rows = values.reshape(len(self.starts), len(self.bins), columns)
        local = rows*self.rotations.conj()[:, :, None]
        result = np.einsum('ij,wjk->wik', self.symmetric, local, optimize=True)
        result *= self.rotations[:, :, None]
        flat = result.reshape(-1, columns)
        return flat[:, 0] if vector else flat

    def apply(self, values):
        return self.transform(self.base.apply(values))

    def sample_matrix(self, start):
        _, local = sample_rows(self.base, 0)
        rotation = np.exp(-2j*np.pi*self.bins*start/self.size)
        transformed = rotation[:, None]*(self.symmetric@local)
        return np.vstack((transformed.real, transformed.imag))

    def adjoint(self, real_values):
        count = len(self.starts)*len(self.bins)
        if real_values.shape != (2*count,):
            raise ValueError('Expected stacked real/imaginary observation vector')
        values = real_values[:count]+1j*real_values[count:]
        rows = values.reshape(len(self.starts), len(self.bins))
        local = np.einsum('ji,wj->wi', self.symmetric, rows*self.rotations.conj(), optimize=True)
        raw = np.zeros(self.frames)
        for index, start in enumerate(self.starts):
            spectrum = np.zeros(self.size//2+1, dtype=complex)
            spectrum[self.bins] = local[index]
            raw[start:start+self.size] += (self.size/self.window.sum())*self.window*np.fft.irfft(spectrum, n=self.size)
        return raw
