"""Source-free transient parameters and fixed-capacity validation."""
from copy import deepcopy
import math

import numpy as np
from scipy import linalg, signal

from event_authoring.contract import validate as validate_modal
from event_authoring.contour_knots import propose

EDGES = ((60, 300), (300, 1200), (1200, 4500), (4500, 14000))
TRAIN_SEEDS = (8123, 20347, 41017, 57037)
HELD_OUT_SEEDS = (12007, 33013, 65003, 91813)


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != {'schema', 'sample_rate', 'modal', 'bands'}:
        raise ValueError('Band texture profile fields do not match')
    if profile['schema'] != 'vsl.event-band-texture/1' or profile['sample_rate'] != 48000:
        raise ValueError('Band texture schema or rate differs')
    modal = validate_modal(profile['modal'])
    if modal['bands'] or modal.get('noise_lowpass_hz', 0):
        raise ValueError('Modal source must contain no legacy noise')
    bands = profile['bands']
    if not isinstance(bands, list) or len(bands) != 4:
        raise ValueError('Four independent bands required')
    for band, edges in zip(bands, EDGES):
        if not isinstance(band, dict) or set(band) != {'hz', 'sos', 'sigma', 'seconds', 'gain'}:
            raise ValueError('Invalid texture band fields')
        if list(edges) != band['hz']:
            raise ValueError('Texture band identity differs')
        sos = np.asarray(band['sos'], dtype=float)
        if sos.ndim != 2 or sos.shape[1] != 6 or not 1 <= len(sos) <= 12 or not np.isfinite(sos).all():
            raise ValueError('Invalid texture SOS')
        if not np.all(sos[:, 3] == 1) or any(max(abs(np.roots(s[3:]))) >= .99995 for s in sos):
            raise ValueError('Unstable texture SOS')
        if isinstance(band['sigma'], bool) or not math.isfinite(band['sigma']) or not 0 < band['sigma'] <= 1e6:
            raise ValueError('Invalid texture innovation scale')
        time, gain = np.asarray(band['seconds']), np.asarray(band['gain'])
        if time.shape != (8,) or gain.shape != (8,) or not np.isfinite(time).all() or not np.isfinite(gain).all():
            raise ValueError('Eight finite amplitude knots required')
        if time[0] != 0 or time[-1] <= 0 or time[-1] > 30 or not np.all(np.diff(time) > 0):
            raise ValueError('Texture knot times must increase from zero')
        if np.any(gain < 0) or np.any(gain > 8):
            raise ValueError('Texture knot gains outside0..8')
    return profile


def vector(profile):
    return np.concatenate([b['gain'] for b in profile['bands']]).astype(float)


def with_vector(profile, values):
    result = deepcopy(profile)
    values = np.asarray(values, dtype=float)
    if values.shape != (32,):
        raise ValueError('Exactly32 texture gains required')
    for index, band in enumerate(result['bands']):
        band['gain'] = values[index*8:(index+1)*8].tolist()
    return validate(result)


def fit_colour(frequency, excess, low, high):
    n = 32768
    hz = np.fft.rfftfreq(n, 1/48000)
    power = np.interp(hz, frequency, excess)
    pad = (high-low)*.1
    weight = np.ones_like(hz)
    left = np.clip((hz-(low-pad))/pad, 0, 1)
    right = np.clip(((high+pad)-hz)/pad, 0, 1)
    weight *= (.5-.5*np.cos(np.pi*left))*(.5-.5*np.cos(np.pi*right))
    covariance = np.fft.irfft(power*weight, n)
    if covariance[0] <= 1e-30:
        raise ValueError('No source colour energy')
    covariance /= covariance[0]
    covariance[0] += .001
    a = np.r_[1., linalg.solve_toeplitz(covariance[:16], -covariance[1:17])]
    sos = np.vstack((signal.tf2sos([1.], a),
                     signal.butter(4, [low, high], fs=48000, btype='bandpass', output='sos')))
    radius = max(max(abs(np.roots(section[3:]))) for section in sos)
    if radius >= .99995:
        raise ValueError('Source colour pole exceeds stability bound')
    _, response = signal.sosfreqz(sos, worN=65536)
    variance = float(np.mean(abs(response)**2)/3)
    sigma = 1/np.sqrt(variance)
    return sos, float(sigma), float(radius)


def design(original, arrays, time, target, rows, duration):
    if not all(row['selected'] for row in rows):
        raise ValueError('Four reliable acoustic bands required')
    modal = deepcopy(original)
    modal['bands'] = []
    modal.pop('noise_lowpass_hz', None)
    result = dict(schema='vsl.event-band-texture/1', sample_rate=48000, modal=modal, bands=[])
    frequency, power, background, *_ = arrays
    excess = np.maximum(power-background, 0)
    measured = []
    for index, (low, high) in enumerate(EDGES):
        sos, sigma, radius = fit_colour(frequency, excess, low, high)
        seconds = propose(time, target[index], duration)
        amplitude = np.sqrt(np.maximum(np.interp(seconds, time, target[index]), 1e-16))
        amplitude /= max(original['level'], 1e-10)
        result['bands'].append(dict(hz=[low, high], sos=sos.tolist(), sigma=sigma,
                                   seconds=seconds, gain=np.clip(amplitude, 1e-8, 8).tolist()))
        measured.append(dict(hz=[low, high], pole_radius=radius, sos_sections=len(sos),
                             theoretical_stationary_variance=1., colour_order=16))
    return validate(result), measured
