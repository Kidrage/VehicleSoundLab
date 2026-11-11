"""Anchored spectral ridge observations, never an automatic engine RPM decoder.

The caller selects a short visible ridge and its initial frequency. Paths may
rise or fall; the algorithm imposes continuity, not an engine/firing model.
"""
from dataclasses import dataclass
import numpy as np
from scipy import signal


@dataclass(frozen=True)
class RidgeSettings:
    window_seconds: float = .128
    hop_seconds: float = .01
    fft_size: int = 32768
    low_hz: float = 60
    high_hz: float = 700
    prominence_db: float = 4
    max_octaves_per_second: float = 2.6
    continuity_cost: float = .15
    anchor_octaves: float = .07
    level_drop_limit_db: float = 25


def spectrogram(audio, rate, settings):
    """Keep channel PSDs; power mean is a selection view, not a waveform mix."""
    x = np.asarray(audio)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Expected finite stereo samples')
    n = round(rate * settings.window_seconds)
    hop = round(rate * settings.hop_seconds)
    if not 0 < hop < n <= settings.fft_size or len(x) < n:
        raise ValueError('Invalid STFT size')
    hz, times, z = signal.stft(x, rate, window='hann', nperseg=n,
        noverlap=n-hop, nfft=settings.fft_size, axis=0, boundary=None,
        padded=False, detrend=False, scaling='psd')
    return hz, times, abs(z)**2


def peak_candidates(hz, power, settings):
    db = 10*np.log10(np.maximum(power, 1e-30))
    peaks, props = signal.find_peaks(db, prominence=settings.prominence_db)
    keep = (hz[peaks] >= settings.low_hz) & (hz[peaks] <= settings.high_hz)
    peaks = peaks[keep]
    prominence = props['prominences'][keep]
    # Parabolic peak interpolation improves location on the padded grid. It
    # does not improve the window's ability to resolve neighbouring tones.
    left, centre, right = db[peaks-1], db[peaks], db[peaks+1]
    denom = left - 2*centre + right
    delta = np.divide(.5*(left-right), denom, out=np.zeros_like(centre),
                      where=abs(denom) > 1e-12)
    delta = np.clip(delta, -.5, .5)
    frequency = hz[peaks]+delta*(hz[1]-hz[0])
    level = centre-.25*(left-right)*delta
    top = np.max(db[(hz >= settings.low_hz) & (hz <= settings.high_hz)])
    emission = -(top-level)/12 + .4*np.minimum(prominence, 24)/24
    return dict(hz=frequency, db=level, prominence=prominence, emission=emission)


def follow(hz, times, power, start, stop, anchor_hz, settings):
    """Maximum-score peak path with one explicit starting anchor.

    No gap interpolation, harmonic relabelling, monotonicity or endpoint
    constraint. Failure returns no path rather than a synthetic trajectory.
    Frame times are window centres; start/stop select centres, not onset times.
    """
    indices = np.flatnonzero((times >= start) & (times <= stop))
    nodes = [peak_candidates(hz, power[:, i], settings) for i in indices]
    if len(indices) < 3 or any(len(n['hz']) == 0 for n in nodes):
        return dict(status='no_connected_path', rows=[])
    initial = abs(np.log2(nodes[0]['hz']/anchor_hz))
    score = np.where(initial <= settings.anchor_octaves,
                     nodes[0]['emission'] - (initial/settings.anchor_octaves)**2,
                     -np.inf)
    links = []
    for j in range(1, len(nodes)):
        dt = times[indices[j]]-times[indices[j-1]]
        velocity = np.log2(nodes[j]['hz'][:, None]/nodes[j-1]['hz'][None, :])/dt
        cost = score[None, :] - settings.continuity_cost*velocity**2
        cost[abs(velocity) > settings.max_octaves_per_second] = -np.inf
        link = np.argmax(cost, axis=1)
        score = cost[np.arange(len(link)), link] + nodes[j]['emission']
        links.append(link)
    if not np.isfinite(score).any():
        return dict(status='no_connected_path', rows=[])
    path = [int(np.argmax(score))]
    for link in reversed(links):
        path.append(int(link[path[-1]]))
    path.reverse()
    levels = np.array([n['db'][k] for n, k in zip(nodes, path)])
    baseline = float(np.median(levels[:max(3, round(.12/settings.hop_seconds))]))
    rows = []
    for i, n, k in zip(indices, nodes, path):
        rows.append(dict(seconds=float(times[i]), hz=float(n['hz'][k]),
            dbfs_per_hz=float(n['db'][k]), prominence_db=float(n['prominence'][k]),
            level_supported=bool(n['db'][k] >= baseline-settings.level_drop_limit_db)))
    return dict(status='connected_peak_path', rows=rows,
        level_baseline_dbfs_per_hz=baseline,
        support_fraction=float(np.mean([r['level_supported'] for r in rows])),
        quality_scope='Continuity/prominence/relative-level diagnostics, not a probability of correct tracking')


def descent_metrics(rows):
    if len(rows) < 3:
        return None
    t = np.array([r['seconds'] for r in rows])
    f = np.array([r['hz'] for r in rows])
    relative = f/f[0]
    slope, intercept = np.polyfit(t-t[0], np.log(f), 1)
    residual = np.log(f)-(intercept+slope*(t-t[0]))
    crossings = np.flatnonzero(relative <= .5)
    half = None
    if len(crossings) and crossings[0] > 0:
        k = crossings[0]
        half = float(np.interp(.5, [relative[k], relative[k-1]],
                               [t[k], t[k-1]])-t[0])
    return dict(centre_seconds=[float(t[0]), float(t[-1])],
        endpoint_hz=[float(f[0]), float(f[-1])],
        endpoint_ratio=float(relative[-1]),
        change_octaves=float(np.log2(relative[-1])),
        mean_octaves_per_second=float(np.log2(relative[-1])/(t[-1]-t[0])),
        log_slope_per_second=float(slope),
        log_fit_rms_cents=float(np.sqrt(np.mean(residual**2))*1200/np.log(2)),
        observed_half_frequency_seconds=half,
        interpretation='Relative frequency descent within selected centres only. Log fit is a descriptive slope, not proof of exponential coastdown or a measured engine time constant.')
