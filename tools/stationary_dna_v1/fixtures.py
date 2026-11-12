"""Independent analytic stereo fixtures with known time-varying acoustic phase."""
import numpy as np
from scipy import signal

RATE = 48000


def make(root, reference, kind, seconds=8):
    t = np.arange(round(seconds*RATE))/RATE
    # Analytic integral in cycles. No estimated clock or inverse-warp utility
    # participates in constructing the original signal.
    phase = root*t
    if kind in ('slow_drift', 'rough_drift'):
        motions = ((.025, .6), (.012, 1.9)) if kind == 'slow_drift' else ((.04, 1.2), (.02, 2.7))
        for depth, hz in motions:
            phase += root*depth*(1-np.cos(2*np.pi*hz*t))/(2*np.pi*hz)
    audio = np.zeros((len(t), 2))
    for k in range(1, 289):
        amp = .014/(1+k/12)**.8
        if k == reference:
            amp = .14
        if k in (1, 2, 3, 5, 6, 10):
            amp = max(amp, .025)
        if kind == 'reference_absent' and k == reference:
            continue
        if kind == 'single_carrier' and k != reference:
            continue
        p = phase
        if kind == 'incompatible_families' and k != reference:
            p = root*1.037*t
        # Unequal amplitudes and nonzero, order-dependent stereo phase.
        level = 1+.12*np.sin(2*np.pi*.73*t+.19*k)
        phi = .37*k+.013*k*k
        audio[:, 0] += amp*level*np.cos(2*np.pi*k*p+phi)
        audio[:, 1] += amp*(.73+.12*np.sin(.2*k))*level*np.cos(2*np.pi*k*p+phi+.17+.021*k)
    rng = np.random.default_rng(619042+reference)
    noise = signal.sosfilt(signal.butter(2, 9000, fs=RATE, output='sos'), rng.normal(size=audio.shape))
    audio += .0025*noise
    return audio, t, phase
