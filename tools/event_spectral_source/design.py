"""Source-derived spectral colour and one modal/noise power-budget initializer."""
from copy import deepcopy

import numpy as np
from scipy import optimize

from event_authoring.contour_knots import propose
from event_authoring.model import synth
from event_band_texture.voice import global_envelope
from .filters import EDGES, colour, stationary_matrix
from .profile import TRAIN_SEEDS, validate
from .measure import curves


def design(original, arrays, time, target, duration, seeds=TRAIN_SEEDS):
    modal = deepcopy(original)
    modal['bands'] = []
    modal.pop('noise_lowpass_hz', None)
    for group in modal.get('contours', []):
        group['gain'] = (np.asarray(group['gain'])*.8).tolist()
    frequency, power, background, *_ = arrays
    excess = np.maximum(power-background, 0)
    bands, radii = [], []
    for low, high in EDGES:
        band, radius = colour(frequency, excess, low, high)
        bands.append(band)
        radii.append(radius)
    matrix = stationary_matrix(bands)
    modal_power = np.mean([curves(synth(modal, seed=s, seconds=duration))[1] for s in seeds], axis=0)
    residual = np.maximum(target-modal_power, 0)
    scale = np.maximum(target.mean(axis=1), float(target.mean(axis=1).sum())*1e-4)
    weights = np.column_stack([optimize.nnls(matrix/scale[:, None], residual[:, k]/scale)[0]
                               for k in range(target.shape[1])])
    amplitude = np.sqrt(np.maximum(weights, 0))
    envelope = global_envelope(modal, round(duration*48000))
    at_time = np.interp(time, np.arange(len(envelope))/48000, envelope)
    amplitude /= np.maximum(at_time, max(modal['level'], 1e-10)*.05)[None, :]
    for index, band in enumerate(bands):
        seconds = propose(time, target[index], duration)
        if len(seconds) != 8:
            raise ValueError('Source supports fewer than eight distinct spectral knots')
        band.update(seconds=seconds,
                    gain=np.clip(np.interp(seconds, time, amplitude[index]), 1e-8, 8).tolist())
    result = validate(dict(schema='vsl.event-spectral-source/1', sample_rate=48000, modal=modal, bands=bands))
    return result, dict(stationary_noise_power_matrix=matrix.tolist(), modal_initializer_fraction=.8,
        pole_radii=radii, initial_modal_power_curves=modal_power.tolist(),
        policy='One nonnegative stationary budget per frame; initializer only, finite cross terms validated later')
