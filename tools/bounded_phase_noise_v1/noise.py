"""Observed upper-band median periodogram proxy; explicitly white-noise only."""
import numpy as np


def estimate(audio, fraction, minimum_bins):
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError('Noise proxy requires a finite real observed channel')
    if not 0 < fraction < 1:
        raise ValueError('Noise proxy fraction must lie inside Nyquist')
    window = .5-.5*np.cos(2*np.pi*np.arange(len(audio))/len(audio))
    frequency = np.fft.rfftfreq(len(audio))
    selected = (frequency >= fraction*.5)&(frequency < .5)
    bins = int(selected.sum())
    if bins < minimum_bins:
        raise ValueError('Insufficient independent-scale upper-band support')
    power = abs(np.fft.rfft(audio*window))**2/np.sum(window**2)
    variance = float(np.median(power[selected])/np.log(2.))
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError('Nonpositive observed noise proxy')
    return dict(variance=variance, standard_deviation=float(np.sqrt(variance)),
        selected_bins=bins, nyquist_fraction=fraction, white_source_noise_assumed=True,
        adjacent_windowed_bins_correlated=True, real_noise_calibrated=False,
        analytic_noise_used=False, heldout_orders_used=False)
