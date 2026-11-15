"""Exact finite weighted-Hann waveform Gram; dense offline prototype only."""
import numpy as np


def finite_gram(frames, starts, window, coverage, amplitude, weights, sigma):
    frames = int(frames)
    window, coverage, weights = (np.asarray(x, float) for x in (window, coverage, weights))
    size = len(window)
    if (frames < size or size % 2 or coverage.shape != (frames,)
            or weights.shape != (size//2+1,) or np.any(coverage <= 0)
            or np.any(weights <= 0) or not amplitude > 0 or not sigma > 0):
        raise ValueError('Invalid finite metric dimensions or positive scales')
    if not all(np.isfinite(x).all() for x in (window, coverage, weights)):
        raise ValueError('Nonfinite finite metric')
    starts = np.asarray(starts)
    if starts.ndim != 1 or np.any(starts != starts.astype(int)) or np.any(starts < 0) or np.any(starts+size > frames):
        raise ValueError('Only original fully supported rows are allowed')
    # The sqrt(2) real-FFT weights are already accounted for by irfft.
    # Unit frequency weights must therefore give the identity circular Gram.
    kernel = np.fft.irfft(weights**2, n=size)
    circular = kernel[(np.arange(size)[:, None]-np.arange(size)[None, :]) % size]
    W = np.zeros((frames, frames))
    np.fill_diagonal(W, 1/sigma**2)
    for start in starts.astype(int):
        gain = amplitude*window/np.sqrt(coverage[start:start+size])
        W[start:start+size, start:start+size] += gain[:, None]*circular*gain[None, :]
    return W


def supported_gram(metric):
    f = metric.frame
    return finite_gram(f.frames, f.starts[metric.keep], f.window, f.coverage,
                       metric.amplitude_scale, metric.weights, metric.wave_scale)
