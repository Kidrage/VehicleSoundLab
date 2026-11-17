"""Generated mono event with independent modal and stochastic amplitude controls."""
from copy import deepcopy

import numpy as np
from scipy import signal

from event_authoring.model import synth, randoms
from event_band_texture.voice import global_envelope
from .profile import validate, vector


def innovations(profile, frames, seed):
    validate(profile)
    if type(seed) is not int or not 1 <= seed <= 4294967295:
        raise ValueError('Spectral seed must be nonzero uint32')
    result = []
    for index, band in enumerate(profile['bands']):
        state = (seed ^ ((0x85ebca6b*(index+1)) & 0xffffffff)) or 0x97bd5821
        noise = randoms(state, 48000+frames)
        result.append(signal.sosfilt(np.asarray(band['sos']), noise*band['sigma'])[48000:])
    value = np.column_stack(result)
    if not np.isfinite(value).all():
        raise ValueError('Nonfinite spectral innovation')
    return value


def basis(profile, seconds, seed):
    validate(profile)
    frames = round(seconds*48000)
    if frames < 2048 or frames > round(profile['modal']['duration_seconds']*48000):
        raise ValueError('Invalid spectral observation duration')
    modal = deepcopy(profile['modal'])
    for group in modal.get('contours', []):
        group['gain'] = [0.]*len(group['gain'])
    constant = synth(modal, seed=seed, seconds=seconds)
    columns = []
    for group in modal.get('contours', []):
        for k in range(len(group['gain'])):
            group['gain'][k] = 1.
            columns.append(synth(modal, seed=seed, seconds=seconds)-constant)
            group['gain'][k] = 0.
    carrier = innovations(profile, frames, seed)
    envelope = global_envelope(profile['modal'], frames)
    t = np.arange(frames)/48000
    for index, band in enumerate(profile['bands']):
        for k in range(8):
            unit = np.zeros(8)
            unit[k] = 1.
            columns.append(carrier[:, index]*np.interp(t, band['seconds'], unit)*envelope)
    return np.column_stack((*columns, constant))


def render(profile, seconds, seed, release_at=None):
    validate(profile)
    frames = round(seconds*48000)
    if frames < 2048 or frames > 30*48000:
        raise ValueError('Invalid spectral render duration')
    if release_at is not None and (not np.isfinite(release_at) or not 0 <= release_at <= seconds):
        raise ValueError('Invalid spectral release time')
    active = min(frames, int(np.ceil(profile['modal']['duration_seconds']*48000)))
    source = innovations(profile, active, seed)
    t = np.arange(active)/48000
    texture = np.zeros(active)
    for index, band in enumerate(profile['bands']):
        texture += source[:, index]*np.interp(t, band['seconds'], band['gain'])
    envelope = global_envelope(profile['modal'], active)
    if release_at is not None:
        left = np.clip(1-(t-release_at)/profile['modal']['release_seconds'], 0, 1)
        envelope *= left*left*(3-2*left)
    modal = synth(profile['modal'], seed=seed, seconds=seconds, release_at=release_at)
    return np.pad(modal+texture*envelope, (0, frames-active))
