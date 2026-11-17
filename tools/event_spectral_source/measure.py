"""Six spectral bands, mean channel powers, fixed periodic-Hann observation."""
import numpy as np
from scipy import signal

from .filters import EDGES


def curves(wave, hop=240):
    value = np.asarray(wave, dtype=float)
    if value.ndim == 1:
        value = value[:, None]
    f, time, psd = signal.spectrogram(value, fs=48000, window='hann', nperseg=2048,
        noverlap=2048-hop, detrend=False, scaling='density', mode='psd', axis=0)
    psd = psd.mean(axis=1)
    return time, np.array([psd[(f >= low)&(f < (high+1 if high == 24000 else high))].sum(axis=0)*(f[1]-f[0])
                           for low, high in EDGES])


def observations(wave, background):
    time, raw = curves(wave)
    _, noise = curves(background)
    target = np.maximum(raw-noise.mean(axis=1)[:, None], 0)
    return time, target
