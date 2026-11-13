"""Exact native finite-window projection adjoint for real vectors or matrices."""
import numpy as np


def native_adjoint(aperture, real_values, frames):
    vector = real_values.ndim == 1
    values = real_values[:, None] if vector else real_values
    count = len(aperture.starts)*len(aperture.bins)
    if len(values) != 2*count:
        raise ValueError('Expected complete stacked real/imaginary native observations')
    rows = (values[:count]+1j*values[count:]).reshape(len(aperture.starts), len(aperture.bins), -1)
    local = rows*aperture.rotations.conj()[:, :, None]
    result = np.zeros((frames, values.shape[1]))
    for index, start in enumerate(aperture.starts):
        spectrum = np.zeros((aperture.size//2+1, values.shape[1]), dtype=complex)
        spectrum[aperture.bins] = local[index]
        result[start:start+aperture.size] += (aperture.size/aperture.window.sum())*aperture.window[:, None]*np.fft.irfft(spectrum, n=aperture.size, axis=0)
    return result[:, 0] if vector else result
