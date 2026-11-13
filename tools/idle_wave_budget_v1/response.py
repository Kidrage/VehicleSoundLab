"""Conditional second/fourth output fields for independent scaled innovations."""
import numpy as np
from scipy.fft import next_fast_len


def kernel_pair(h, b, c, lag):
    """Index u belongs to the first output at n; second output is n+lag."""
    size = h.shape[2]
    first, last = max(0, -lag), min(size, size-lag)
    product = np.zeros((size, h.shape[1]))
    if last > first:
        product[first:last] = (h[b, :, first:last]*h[c, :, first+lag:last+lag]).T
    return product


class Fields:
    def __init__(self, h, variance, warmup, frames, kappa, stationary=False):
        self.h, self.v = np.asarray(h), np.asarray(variance)
        self.warmup, self.frames, self.kappa = warmup, frames, np.asarray(kappa)
        self.stationary = stationary
        if self.v.shape != (warmup+frames, h.shape[1]) or np.any(self.v <= 0) or not np.isfinite(self.v).all():
            raise ValueError('Positive finite input variances required')
        if warmup < h.shape[2]-1:
            raise ValueError('Warmup must cover the full effective response')
        self.size = next_fast_len(len(self.v)+h.shape[2]-1)
        if stationary:
            if not np.array_equal(self.v, np.ones_like(self.v)):
                raise ValueError('Stationary shortcut requires exact unit variance')
        else:
            self.V = np.fft.rfft(self.v, n=self.size, axis=0)
            self.V2 = np.fft.rfft(self.v*self.v, n=self.size, axis=0)

    def pair(self, b, c, lag):
        product = kernel_pair(self.h, b, c, lag)
        if self.stationary:
            covariance = np.full(self.frames, product.sum())
            cumulant = np.full(self.frames, np.sum(product*product*self.kappa))
            return covariance, cumulant
        H = np.fft.rfft(product, n=self.size, axis=0)
        H4 = np.fft.rfft(product*product*self.kappa, n=self.size, axis=0)
        covariance = np.fft.irfft(np.sum(H*self.V, axis=1), n=self.size)
        cumulant = np.fft.irfft(np.sum(H4*self.V2, axis=1), n=self.size)
        section = slice(self.warmup, self.warmup+self.frames)
        return covariance[section], cumulant[section]

    def variances(self):
        return np.column_stack([self.pair(b, b, 0)[0] for b in range(self.h.shape[0])])
