"""Compare repeated mixed recordings at a supplied observed ridge frequency.

The coordinate is not engine RPM. No source separation or waveform rewriting.
"""
import numpy as np
from scipy import signal


def descending_crossings(rows, targets):
    t = np.asarray([r['seconds'] for r in rows], dtype=float)
    f = np.asarray([r['hz'] for r in rows], dtype=float)
    if len(t) < 3 or not np.all(np.diff(t) > 0) or not np.isfinite(f).all() or np.any(f <= 0):
        raise ValueError('Finite positive ridge and increasing times required')
    output = []
    for target in targets:
        indices = np.flatnonzero((f[:-1] >= target) & (f[1:] < target))
        if len(indices) != 1:
            output.append(dict(target_hz=float(target), status='ambiguous_or_missing_crossing',
                               crossing_count=len(indices)))
            continue
        i = int(indices[0])
        w = (target-f[i])/(f[i+1]-f[i])
        output.append(dict(target_hz=float(target), status='single_descending_crossing',
            seconds=float(t[i]+w*(t[i+1]-t[i])),
            bracket_seconds=t[i:i+2].tolist(), bracket_hz=f[i:i+2].tolist()))
    return output


def at_times(frame_times, values, query_times):
    """Interpolate analysis matrices only; never extrapolate or resample audio."""
    t, q, v = np.asarray(frame_times), np.asarray(query_times), np.asarray(values)
    if len(t) != len(v) or not np.all(np.diff(t) > 0) or not np.isfinite(v).all():
        raise ValueError('Invalid spectral matrix')
    if np.any(q < t[0]) or np.any(q > t[-1]):
        raise ValueError('Query outside STFT support')
    flat = v.reshape(len(t), -1)
    return np.column_stack([np.interp(q, t, flat[:, i]) for i in range(flat.shape[1])]).reshape((len(q),)+v.shape[1:])


def shape_difference(frequency, first, second, bounds=(1500, 8000)):
    f, a, b = np.asarray(frequency), np.asarray(first), np.asarray(second)
    if a.shape != b.shape or a.shape[-1] != len(f) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Equal finite log-PSD matrices required')
    use = (f >= bounds[0]) & (f <= bounds[1])
    if np.count_nonzero(use) < 2:
        raise ValueError('Insufficient bins')
    delta = b[..., use]-a[..., use]
    offset = delta.mean(axis=-1)
    shape = delta-offset[..., None]
    return dict(mean_log_PSD_change_db=offset.tolist(),
                mean_removed_shape_RMS_db=np.sqrt(np.mean(shape**2, axis=-1)).tolist(),
                bins=int(use.sum())), shape


def window_band_powers(audio, rate, seconds, window_seconds, bands):
    """One-sided raw-Hz PSD integrals; Hann weighted mean-square, not log shape."""
    x = np.asarray(audio)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Unchanged finite stereo required')
    n = round(window_seconds*rate)
    first = round(seconds*rate)-n//2
    if first < 0 or first+n > len(x):
        raise ValueError('Window outside audio')
    w = signal.windows.hann(n, sym=False)
    block = x[first:first+n]*w[:, None]
    z = np.fft.rfft(block, axis=0)
    p = abs(z)**2/(rate*np.dot(w, w))
    if n % 2:
        p[1:] *= 2
    else:
        p[1:-1] *= 2
    hz = np.fft.rfftfreq(n, 1/rate)
    df = rate/n
    total = p.sum(axis=0)*df
    direct = (block**2).sum(axis=0)/np.dot(w, w)
    error = float(np.max(abs(total-direct)))
    if not np.allclose(total, direct, rtol=2e-12, atol=1e-18):
        raise AssertionError('Parseval mismatch')
    power = [p[(hz >= lo) & (hz < hi)].sum(axis=0)*df for lo, hi in bands]
    return np.asarray(power), dict(first_frame=first, stop_frame=first+n,
        window_centre_seconds=(first+n/2)/rate, parseval_max_error=error)
