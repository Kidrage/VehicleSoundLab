"""Recording-domain observations; none is a perceptual realism score."""
import numpy as np
from scipy import signal

BANDS = [(80, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 14000)]


def describe(audio, rate):
    frequency, psd = signal.welch(audio, rate, nperseg=4096, axis=0)
    power = psd.mean(axis=1)
    step = frequency[1]-frequency[0]
    return dict(rms_dbfs=float(10*np.log10(max(np.mean(audio*audio), 1e-30))),
        peak=float(abs(audio).max()), channel_correlation=float(np.corrcoef(audio.T)[0, 1]),
        band_power_db={f'{lo}-{hi}':float(10*np.log10(max(
            power[(frequency >= lo)&(frequency < hi)].sum()*step, 1e-30))) for lo, hi in BANDS})


def compare(reference, approximation, rate):
    valid = slice(rate//5, -rate//5)
    x, y = reference[valid], approximation[valid]
    return dict(relative_waveform_residual_db=float(10*np.log10(max(
        np.mean((x-y)**2), 1e-30)/max(np.mean(x*x), 1e-30))),
        reference=describe(x, rate), reconstruction=describe(y, rate),
        limit='Same-excerpt waveform and band diagnostics, including unmodelled noise/transfer/tracking errors. Not held-out engine generalization, physical source separation or perceptual reproduction percentage.')
