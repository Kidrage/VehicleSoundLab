"""Same source FIR and genuine crop; normalized bandlimited fractional queries."""
import numpy as np
from scipy import signal


def prepare(audio, source_start, positions, cutoff):
    audio, positions = np.asarray(audio), np.asarray(positions)
    if (audio.ndim != 2 or audio.shape[1] != 2 or np.iscomplexobj(audio)
            or not np.isfinite(audio).all() or positions.ndim != 1 or not len(positions)
            or np.iscomplexobj(positions) or not np.isfinite(positions).all()
            or np.any(np.diff(positions) <= 0) or not np.isfinite(source_start)
            or not np.isfinite(cutoff) or not 0 < cutoff <= 14000):
        raise ValueError('Finite48k stereo, increasing common queries and declared cutoff required')
    first = int(np.floor((positions[0]-source_start)*48000+1e-6))-4800
    stop = int(np.ceil((positions[-1]-source_start)*48000-1e-6))+4801
    if first < 0 or stop > len(audio):
        raise ValueError('Need100ms genuine source context around every query')
    taps = signal.firwin(1025, cutoff, fs=48000, window=('kaiser', 12))
    filtered = signal.fftconvolve(audio[first:stop], taps[:, None], mode='same', axes=0)
    query = (positions-source_start-first/48000)*48000
    return filtered, query, taps, (first, stop)


def interpolate(filtered, query, radius):
    if type(radius) is not int or radius not in (64, 128, 256):
        raise ValueError('Declared64/128/256 radius required')
    filtered, query = np.asarray(filtered), np.asarray(query)
    if (filtered.ndim != 2 or filtered.shape[1] != 2 or np.iscomplexobj(filtered)
            or not np.isfinite(filtered).all() or query.ndim != 1 or not len(query)
            or np.iscomplexobj(query) or not np.isfinite(query).all()):
        raise ValueError('Finite real stereo and queries required')
    centers = np.floor(query).astype(np.int64)
    offsets = np.arange(1-radius, radius+1)
    if centers.min()+offsets[0] < 0 or centers.max()+offsets[-1] >= len(filtered):
        raise ValueError('Genuine interpolation support required')
    result = np.empty((len(query), 2))
    for first in range(0, len(query), 2048):
        q = query[first:first+2048]
        indices = centers[first:first+len(q), None]+offsets[None]
        d = q[:, None]-indices
        weights = np.sinc(d)*np.i0(12*np.sqrt(1-(d/radius)**2))/np.i0(12.)
        weights /= weights.sum(axis=1)[:, None]
        result[first:first+len(q)] = np.einsum('ij,ijc->ic', weights, filtered[indices], optimize=True)
    return result
