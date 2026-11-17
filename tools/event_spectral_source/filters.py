"""Stable source colour with explicit lowpass, bandpass and highpass edges."""
import numpy as np
from scipy import linalg, signal

EDGES = ((0, 60), (60, 300), (300, 1200), (1200, 4500), (4500, 14000), (14000, 24000))


def colour(frequency, excess, low, high):
    n = 32768
    hz = np.fft.rfftfreq(n, 1/48000)
    measured = np.interp(hz, frequency, excess)
    width = (high-low)*.1
    weight = np.ones_like(hz)
    if low:
        left = np.clip((hz-(low-width))/width, 0, 1)
        weight *= .5-.5*np.cos(np.pi*left)
    if high < 24000:
        right = np.clip(((high+width)-hz)/width, 0, 1)
        weight *= .5-.5*np.cos(np.pi*right)
    covariance = np.fft.irfft(measured*weight, n)
    if covariance[0] <= 1e-30:
        raise ValueError('No positive source power for spectral colour')
    covariance /= covariance[0]
    covariance[0] += .001
    denominator = np.r_[1., linalg.solve_toeplitz(covariance[:16], -covariance[1:17])]
    if low == 0:
        post = signal.butter(4, high, btype='lowpass', fs=48000, output='sos')
    elif high == 24000:
        post = signal.butter(4, low, btype='highpass', fs=48000, output='sos')
    else:
        post = signal.butter(4, [low, high], btype='bandpass', fs=48000, output='sos')
    sos = np.vstack((signal.tf2sos([1.], denominator), post))
    radius = float(max(max(abs(np.roots(section[3:]))) for section in sos))
    if not np.isfinite(sos).all() or radius >= .99995:
        raise ValueError('Spectral colour exceeds stability bound')
    _, response = signal.sosfreqz(sos, worN=65536)
    sigma = float(1/np.sqrt(np.mean(abs(response)**2)/3))
    return dict(hz=[low, high], sos=sos.tolist(), sigma=sigma), radius


def stationary_matrix(bands):
    columns = []
    for band in bands:
        hz, response = signal.sosfreqz(np.asarray(band['sos']), worN=65536, fs=48000)
        power = abs(response)**2*band['sigma']**2/3/len(hz)
        columns.append([power[(hz >= low)&(hz < high)].sum() for low, high in EDGES])
    return np.asarray(columns).T
