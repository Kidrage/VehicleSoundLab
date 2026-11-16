"""Explicit22k physical FIR and long supported native source queries."""
import numpy as np
from scipy import signal
from locked_source_tail_v1.kernel import reference


def sample(audio, source_start, positions):
    audio, positions = np.asarray(audio), np.asarray(positions)
    if (audio.ndim != 2 or audio.shape[1] != 2 or np.iscomplexobj(audio)
            or not np.isfinite(audio).all() or positions.ndim != 1 or not len(positions)
            or np.iscomplexobj(positions) or not np.isfinite(positions).all()
            or np.any(np.diff(positions) <= 0) or not np.isfinite(source_start)):
        raise ValueError('Finite native48k stereo and increasing common LR source times required')
    first = int(np.floor((positions[0]-source_start)*48000+1e-6))-4800
    stop = int(np.ceil((positions[-1]-source_start)*48000-1e-6))+4801
    if first < 0 or stop > len(audio):
        raise ValueError('Every source query requires100ms genuine source support')
    taps = signal.firwin(1025, 22000., fs=48000, window=('kaiser', 12))
    filtered = signal.fftconvolve(audio[first:stop], taps[:, None], mode='same', axes=0)
    query = (positions-source_start-first/48000)*48000
    result = reference(filtered, query, 2048)
    return dict(audio=result, filtered=filtered, query=query, taps=taps,
                crop=np.array([first, stop]), radius=np.array(2048), beta=np.array(20.))
