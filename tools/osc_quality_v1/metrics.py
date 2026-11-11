"""Signal diagnostics; none is a perceptual quality or realism percentage."""
import numpy as np
from scipy import signal


def relative_error(reference, reconstructed, rate):
    x, y = reference[rate//5:-rate//5], reconstructed[rate//5:-rate//5]
    return float(10*np.log10(max(np.mean((x-y)**2), 1e-30)/max(np.mean(x*x), 1e-30)))


def modulation_amplitude(audio, rate, carrier, modulation):
    t = np.arange(len(audio))/rate
    shifted = audio*np.exp(-2j*np.pi*carrier*t)*2
    envelope = abs(signal.sosfiltfilt(signal.butter(6, 80, fs=rate, output='sos'), shifted))
    valid = slice(rate//2, -rate//2)
    return float(abs(np.sum(envelope[valid]*np.exp(-2j*np.pi*modulation*t[valid])))*2/len(t[valid]))


def spectral_diagnostics(reference, approximation, rate):
    n, hop = 1024, 128
    f, t, zx = signal.stft(reference, rate, nperseg=n, noverlap=n-hop, boundary=None)
    _, _, zy = signal.stft(approximation, rate, nperseg=n, noverlap=n-hop, boundary=None)
    valid_t = (t > .2)&(t < len(reference)/rate-.2)
    valid_f = (f >= 80)&(f < 8000)
    x, y = abs(zx[valid_f][:, valid_t])**2, abs(zy[valid_f][:, valid_t])**2
    db = 10*np.log10((y+1e-30)/(x+1e-30))
    support = x > x.max(axis=0)*10**(-50/10)
    return dict(time_frequency_hole_fraction=float(np.mean(db[support] < -15)),
        time_frequency_excess_fraction=float(np.mean(db[support] > 10)),
        median_absolute_local_power_error_db=float(np.median(abs(db[support]))),
        definition='1024 Hann/128hop;80-8000Hz; reference bins within50dB of each frame peak. Hole <-15dB, excess >10dB. Includes leakage, transients and tracking errors; no physical-source or perceptual identification.')
