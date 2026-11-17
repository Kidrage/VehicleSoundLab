"""Source-free modal-plus-texture contract, at most80 amplitude controls."""
from copy import deepcopy
import math

import numpy as np

from event_authoring.contract import validate as validate_modal
from .filters import EDGES

TRAIN_SEEDS = (9151, 25717, 49223, 61253)
HELD_OUT_SEEDS = (16519, 36109, 78467, 101111)


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != {'schema', 'sample_rate', 'modal', 'bands'}:
        raise ValueError('Spectral source fields differ')
    if profile['schema'] != 'vsl.event-spectral-source/1' or profile['sample_rate'] != 48000:
        raise ValueError('Spectral source schema or rate differs')
    modal = validate_modal(profile['modal'])
    if modal['bands'] or modal.get('noise_lowpass_hz', 0):
        raise ValueError('Modal component must contain no legacy noise')
    if not isinstance(profile['bands'], list) or len(profile['bands']) != 6:
        raise ValueError('Six spectral branches required')
    for band, edges in zip(profile['bands'], EDGES):
        if not isinstance(band, dict) or set(band) != {'hz', 'sos', 'sigma', 'seconds', 'gain'}:
            raise ValueError('Invalid spectral branch fields')
        if band['hz'] != list(edges):
            raise ValueError('Spectral branch identity differs')
        sos = np.asarray(band['sos'], dtype=float)
        if sos.ndim != 2 or sos.shape[1] != 6 or not 1 <= len(sos) <= 12 or not np.isfinite(sos).all():
            raise ValueError('Invalid spectral SOS')
        if np.any(sos[:, 3] != 1) or any(max(abs(np.roots(s[3:]))) >= .99995 for s in sos):
            raise ValueError('Unstable spectral SOS')
        if isinstance(band['sigma'], bool) or not math.isfinite(band['sigma']) or not 0 < band['sigma'] <= 1e6:
            raise ValueError('Invalid spectral innovation scale')
        time, gain = np.asarray(band['seconds']), np.asarray(band['gain'])
        if time.shape != (8,) or gain.shape != (8,) or not np.isfinite(time).all() or not np.isfinite(gain).all():
            raise ValueError('Eight finite spectral knots required')
        if time[0] != 0 or time[-1] > 30 or time[-1] <= 0 or not np.all(np.diff(time) > 0):
            raise ValueError('Invalid spectral knot times')
        if np.any(gain < 0) or np.any(gain > 8):
            raise ValueError('Spectral gains outside0..8')
    return profile


def groups(profile):
    return [*profile['modal'].get('contours', []), *profile['bands']]


def vector(profile):
    return np.concatenate([group['gain'] for group in groups(profile)]).astype(float)


def with_vector(profile, values):
    result = deepcopy(profile)
    values = np.asarray(values, dtype=float)
    sizes = [len(group['gain']) for group in groups(result)]
    if values.shape != (sum(sizes),):
        raise ValueError('Spectral amplitude count differs')
    offset = 0
    for group, size in zip(groups(result), sizes):
        group['gain'] = values[offset:offset+size].tolist()
        offset += size
    return validate(result)
