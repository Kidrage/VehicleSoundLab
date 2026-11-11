"""Explicit known coherent OSC fixtures, separate from real-recording models."""
import numpy as np
from state_colour_v2.features import BANDS

ORDERS = np.arange(1, 289)
CENTERS = np.sqrt(np.array(BANDS)[:, 0] * np.array(BANDS)[:, 1]) / 46.875
KNOWN_GAIN = 10 ** (np.interp(np.log2(ORDERS), np.log2(CENTERS), [-5, -3, 2, 4, 6]) / 20)


def coefficients(resolved=True):
    amp = .03 / (1 + (ORDERS / 12) ** 1.3)
    phase = .2 * np.sin(ORDERS)
    z = amp[:, None] * np.exp(1j * np.column_stack((phase, phase + .4 * np.sin(ORDERS * .3))))
    z[:, 1] *= .8 + .1 * np.sin(ORDERS)
    if resolved: z[[2, 4, 6]] *= np.array([3., 6., 2.])[:, None]
    return z


def source(curve, falling=False, gain=None, noise=False, contaminated=False, missing=False, resolved=True):
    duration = .38 if curve.startswith('rapid') else .8
    times = np.arange(round((duration + .4) * 48000) + 1) / 48000
    u = np.clip((times - .2) / duration, 0, 1)
    if falling: u = 1-u
    if curve == 'linear': roots = 25 + 45*u
    elif curve == 'exponential': roots = 25*(70/25)**u
    elif curve == 'rapid_curve': roots = 25 + 45*(3*u*u-2*u*u*u)
    elif curve == 'rapid_corner': roots = np.interp(u, [0, .32, .53, .68, 1], [25, 30, 50, 63, 70])
    else: raise ValueError(curve)
    phase = np.r_[0., np.cumsum((roots[1:] + roots[:-1]) / 96000)]
    z = coefficients(resolved)
    if missing: z[:] = 0;z[6] = [.2, .15*np.exp(.3j)]
    audio = np.zeros((len(times), 2))
    if gain is None: gain = np.ones(288)
    for h in range(288):
        angle = 2*np.pi*(h+1)*phase
        if contaminated and h == 4: angle += 1.2*np.sin(2*np.pi*6*times)
        audio += np.real(np.exp(1j*angle)[:, None]*z[h]*gain[h])
    if noise:
        rng=np.random.default_rng(91731)
        audio += rng.standard_normal(audio.shape)*np.sqrt(np.mean(audio**2))*10**(-30/20)
    return audio, times, roots, [.2, .2+duration], z
