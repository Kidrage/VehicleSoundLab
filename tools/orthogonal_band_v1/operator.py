"""One orthogonal finite-record band with native-Hann white-noise row units."""
import numpy as np


class OrthogonalBand:
    def __init__(self, frames, plan):
        self.frames = int(frames)
        samples_per_cycle = plan['samples_per_cycle']
        duration = self.frames/samples_per_cycle
        low, high = np.asarray(plan['observed_order_range'])*duration
        self.bins = np.arange(int(np.ceil(low-1e-10)), int(np.floor(high+1e-10))+1)
        if not len(self.bins) or self.bins[0] <= 0 or self.bins[-1] >= self.frames/2:
            raise ValueError('An interior positive-frequency band is required')
        self.orders = self.bins/duration
        original_size = round(plan['projection_cycles']*samples_per_cycle)
        original_window = .5-.5*np.cos(2*np.pi*np.arange(original_size)/original_size)
        self.row_variance = float(2*np.sum(original_window**2)/original_window.sum()**2)
        self.factor = np.sqrt(2*self.row_variance/self.frames)

    def apply(self, values):
        if values.shape[0] != self.frames:
            raise ValueError('Wrong source sample count')
        return self.factor*np.fft.rfft(values, axis=0)[self.bins]

    def adjoint(self, values):
        if values.shape[0] != 2*len(self.bins):
            raise ValueError('Expected stacked real/imaginary rows')
        count = len(self.bins)
        spectrum = np.zeros((self.frames//2+1,)+values.shape[1:], dtype=complex)
        spectrum[self.bins] = values[:count]+1j*values[count:]
        return self.factor*self.frames/2*np.fft.irfft(spectrum, n=self.frames, axis=0)
