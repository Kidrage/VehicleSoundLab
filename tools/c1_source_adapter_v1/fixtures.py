"""Same analytic physical stereo source sampled by old PL and new C1 clocks."""
import numpy as np
from scipy import signal
from clock_c1_v1.geometry import build, evaluate
from locked_source_tail_v1.known import evaluate as analytic
from locked_source_fit_v1.adapter import build as original_build


def cases():
    for label, size in (('affine_unequal', 4609), ('nonlinear_delay', 4353),
        ('nonlinear_silent_right', 4865), ('nonlinear_zero', 4609)):
        n = size+4096; q = np.arange(n, dtype=float)
        x = np.unique(np.r_[np.arange(0, n, 256), n-1]).astype(float)
        y = 160.36+x/65536
        if label != 'affine_unequal': y += 8e-8*np.sin(x/750)
        clock = build(x, y); old_times = np.interp(q, x, y); new_times = evaluate(clock, q)
        orders = np.array([5, 65, 110, 140, 185, 300])
        scale = np.array([.19, .13, .09, .08, .06, .04])[:, None]
        frequency = orders*64.
        coeff = np.array([[scale[i, 0]*np.exp(.29j*i), .61*scale[i, 0]*np.exp(1j*(1.1+.81*i))] for i in range(6)])
        if label == 'nonlinear_delay': coeff[:, 1] = .63*coeff[:, 0]*np.exp(-2j*np.pi*frequency*.00035)
        if label == 'nonlinear_silent_right': coeff[:, 1] = 0
        if label == 'nonlinear_zero': coeff[:] = 0
        taps = signal.firwin(1025, 22000, fs=48000, window=('kaiser', 12))
        old_audio = analytic(old_times-160., frequency, coeff, taps)
        new_audio = analytic(new_times-160., frequency, coeff, taps)
        original = np.array([0, int(.167*(size-1)), int(.433*(size-1)), int(.709*(size-1)), size-1])
        system, shared, reference = original_build(old_audio, old_audio[2048:-2048],
            old_audio[2048:-2048], original, orders, scale)
        m = system.metric
        legacy = dict(audio=old_audio, target=old_audio[2048:-2048].copy(), metric_target=old_audio[2048:-2048].copy(),
            positions=system.synthesis.positions.copy(), original_positions=original, orders=orders, scale=scale,
            source_coordinates=old_times, target_source_coordinates=old_times[2048:-2048].copy(),
            weights=m.weights.copy(), band_power=m.band_power.copy(), floor_active=m.floor_active.copy(),
            sigma=np.array(m.wave_scale), amplitude=np.array(m.amplitude_scale))
        yield dict(label=label, legacy=legacy, observations=dict(x=x, y=y), clock=clock,
            new_audio=new_audio, taps=taps, cutoff=22000., frequency=frequency, coefficients=coeff)
