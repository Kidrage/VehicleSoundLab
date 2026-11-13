"""Independent acoustic-mode features and band power; no engine phase inference."""
import numpy as np
from scipy import signal


def average(x, frames):
    n = len(x)//frames
    return np.asarray(x)[:n*frames].reshape(n, frames, *np.shape(x)[1:]).mean(axis=1)


def phases(x, frequencies, rate=48000):
    result=[]
    for frequency in frequencies:
        sos=signal.butter(4, [frequency-10, frequency+10], btype='bandpass', fs=rate, output='sos')
        analytic=signal.hilbert(signal.sosfiltfilt(sos, x))
        if np.any(abs(analytic)==0):
            raise ValueError('Undefined acoustic phasor; no gap fill')
        result.append(analytic/abs(analytic))
    return np.asarray(result).T


def observe(x, frequencies, bands, hop=48, trim=12000, rate=48000):
    phasors=phases(x[:,0], frequencies, rate)
    feature=np.column_stack((phasors.real, phasors.imag))
    filtered=np.column_stack([signal.sosfilt(signal.butter(4, band, btype='bandpass',
        fs=rate, output='sos'), x[:,0]) for band in bands])
    return average(feature[trim:-trim],hop), average(filtered[trim:-trim]**2,hop), phasors

