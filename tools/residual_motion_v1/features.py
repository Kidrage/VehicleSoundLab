"""Band-amplitude observations; overlapping frames are not independent trials."""
import numpy as np
from residual_osc_v1.spectrum import BANDS

SIZE = 2048
HOP = 480


def powers(audio):
    starts = np.arange(0, len(audio)-SIZE+1, HOP)
    window = .5-.5*np.cos(2*np.pi*np.arange(SIZE)/SIZE)
    hz = np.fft.rfftfreq(SIZE, 1/48000)
    frames = audio[starts[:, None]+np.arange(SIZE)]*window[None, :, None]
    z = np.fft.rfft(frames, axis=1)
    power = abs(z)**2/(SIZE*np.sum(window**2))
    power[:, 1:-1] *= 2
    bands = np.array([power[:, (hz >= lo) & (hz < hi)].sum(axis=1) for lo, hi in BANDS]).transpose(1, 0, 2)
    return (starts+SIZE/2)/48000, bands


def amplitudes(power):
    pooled = np.mean(power, axis=2)
    return np.sqrt(np.maximum(pooled, 1e-30)/np.maximum(pooled.mean(axis=0), 1e-30))


def covariance(amplitude):
    # Remove one linear trend per observation; this is an explicit engineering
    # separation of slow passage evolution, not measured steady engine load.
    at = np.linspace(-1, 1, len(amplitude))
    design = np.column_stack((np.ones(len(at)), at))
    fitted = design@np.linalg.lstsq(design, amplitude, rcond=None)[0]
    centered = amplitude-fitted
    return centered.T@centered/(len(centered)-1), centered[:-1].T@centered[1:]/(len(centered)-1)
