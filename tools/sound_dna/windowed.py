"""Tapered multi-cycle analysis for sources with a weak high-frequency band."""
import numpy as np
from .statistics import factorize


def coefficients(audio, harmonics, cycles=4):
    if not 1 <= harmonics <= 320 or not 2 <= cycles <= 8:
        raise ValueError('Invalid harmonic / cycle count')
    size=1024*cycles
    if len(audio) < size+256:
        raise ValueError('Insufficient cycles for tapered observations')
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    k=np.arange(1,harmonics+1)
    rows=[]
    for start in range(0,len(audio)-size+1,256):
        z=np.fft.rfft(audio[start:start+size]*window[:,None],axis=0)[k*cycles]*2/window.sum()*np.exp(-2j*np.pi*k*start/1024)[:,None]
        rows.append(np.column_stack([z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag]).ravel())
    return np.asarray(rows)


def estimate(audio,harmonics,components,cycles=4):
    if not 0 <= components <= 16:
        raise ValueError('Invalid component count')
    model,stats=factorize(coefficients(audio,harmonics,cycles),harmonics,components)
    stats.update(window='periodic Hann',analysis_cycles=cycles,window_samples=cycles*1024,
        amplitude_normalization='2/sum(window); exact response at integer acoustic harmonics',
        warning='Taper suppresses boundary leakage; does not isolate physical sources or preserve arbitrary inharmonic detail')
    return model,stats
