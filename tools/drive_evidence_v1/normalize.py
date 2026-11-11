"""Common stereo time warp into an explicit acoustic cycle coordinate."""
import numpy as np
from scipy import signal


def cycles(audio, segment_start, clock_seconds, root_hz, start, stop):
    rate = 48000
    if not (clock_seconds[0] <= start < stop <= clock_seconds[-1]):
        raise ValueError('Never extrapolate an observed clock')
    times = np.arange(round(start*rate), round(stop*rate)+1)/rate
    frequency = np.interp(times, clock_seconds, root_hz)
    phase = np.r_[0., np.cumsum((frequency[:-1]+frequency[1:])/(2*rate))]
    position = np.interp(np.arange(int(phase[-1]*1024))/1024, phase, times)
    first = round((start-segment_start-.1)*rate)
    last = round((stop-segment_start+.1)*rate)
    if first < 0 or last > len(audio):
        raise ValueError('Need100ms real context on both ends')
    taps = signal.firwin(1025, 14000, fs=rate, window=('kaiser', 12))
    filtered = signal.fftconvolve(audio[first:last], taps[:, None], mode='same', axes=0)
    dense = signal.resample_poly(filtered, 16, 1, axis=0, window=('kaiser', 8.6), padtype='line')
    at = (position-segment_start-first/rate)*rate*16
    normalized = np.column_stack([np.interp(at, np.arange(len(dense)), dense[:, channel]) for channel in (0, 1)])
    return normalized, dict(source_seconds=[start, stop], root_hz_range=[float(frequency.min()), float(frequency.max())],
        root_hz_median=float(np.median(frequency)), normalized_frames=len(normalized),
        complete_cycles=len(normalized)//1024,
        normalized_playback_root_hz=46.875,
        processing='Shared stereo acoustic-cycle warp;14kHz FIR and16x Kaiser interpolation; no highpass, normalization, compression, room or channel folding',
        coordinate='Observed reference line /5; E display agreement supports a2.5-order hypothesis for the reference line, not precision RPM or physical source separation')
