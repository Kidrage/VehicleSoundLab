"""New generated innovations, fixed spectral colour, then time envelope."""
import numpy as np
from scipy import signal

from event_authoring.model import randoms, synth
from .profile import validate


def global_envelope(modal, frames):
    age = np.arange(frames)
    attack = np.ones(frames) if not modal['attack_seconds'] else np.clip(
        age/(48000*modal['attack_seconds']), 0, 1)
    attack = attack*attack*(3-2*attack)
    duration = int(np.ceil(modal['duration_seconds']*48000))
    left = np.clip((duration-age)/(48000*modal['release_seconds']), 0, 1)
    return attack*left*left*(3-2*left)*modal['level']


def carriers(profile, frames, seed):
    validate(profile)
    if type(seed) is not int or not 1 <= seed <= 4294967295:
        raise ValueError('Texture seed must be nonzero uint32')
    warm = 48000
    result = []
    for index, band in enumerate(profile['bands']):
        stream = (seed ^ ((0x9e3779b9*(index+1)) & 0xffffffff)) or 0x97bd5821
        noise = randoms(stream, warm+frames)
        wave = signal.sosfilt(np.asarray(band['sos']), noise*band['sigma'])[warm:]
        if not np.isfinite(wave).all():
            raise ValueError('Nonfinite texture filter output')
        result.append(wave)
    return np.column_stack(result)


def basis(profile, seconds, seed):
    validate(profile)
    frames = round(seconds*48000)
    if frames < 2048 or frames > round(profile['modal']['duration_seconds']*48000):
        raise ValueError('Observation outside event duration')
    source = carriers(profile, frames, seed)
    constant = synth(profile['modal'], seed=seed, seconds=seconds)
    envelope = global_envelope(profile['modal'], frames)
    time = np.arange(frames)/48000
    columns = []
    for index, band in enumerate(profile['bands']):
        for k in range(8):
            unit = np.zeros(8)
            unit[k] = 1
            control = np.interp(time, band['seconds'], unit)
            columns.append(source[:, index]*control*envelope)
    return np.column_stack((*columns, constant))


def render(profile, seconds, seed, release_at=None):
    # Separate direct implementation from basis construction for validation.
    validate(profile)
    frames = round(seconds*48000)
    if frames < 2048 or frames > 30*48000:
        raise ValueError('Invalid event render duration')
    if release_at is not None and (not np.isfinite(release_at) or not 0 <= release_at <= seconds):
        raise ValueError('Invalid event release time')
    active = min(frames, int(np.ceil(profile['modal']['duration_seconds']*48000)))
    sources = carriers(profile, active, seed)
    t = np.arange(active)/48000
    texture = np.zeros(active)
    for i, band in enumerate(profile['bands']):
        texture += sources[:, i]*np.interp(t, band['seconds'], band['gain'])
    envelope = global_envelope(profile['modal'], active)
    if release_at is not None:
        left = np.clip(1-(t-release_at)/profile['modal']['release_seconds'], 0, 1)
        envelope *= left*left*(3-2*left)
    wave = synth(profile['modal'], seed=seed, seconds=seconds, release_at=release_at)+texture*envelope
    return np.pad(wave, (0, frames-active))
