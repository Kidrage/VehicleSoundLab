"""Conditional smooth-spectrum models in fixed-Hz and moving coordinates.

The given ridge is a conditioning coordinate, never identified engine RPM.
Per-frame log levels are projected out; this predicts shape, not loudness.
"""
from dataclasses import dataclass, asdict
import numpy as np
from scipy import signal, ndimage


@dataclass(frozen=True)
class ShapeSettings:
    window_seconds: float = .08533333333333333
    hop_seconds: float = .01
    spectrum_hz: tuple = (600., 14000.)
    evaluate_hz: tuple = (1500., 8000.)
    bins_per_octave: int = 48
    smoothing_octaves: float = .125
    knot_octaves: float = 1/12
    curvature_penalty: float = .1
    purge_seconds: float = .192
    test_frames: int = 10
    minimum_train_frames: int = 12


def smooth_spectra(audio, rate, settings=ShapeSettings()):
    x = np.asarray(audio)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Finite unchanged stereo required')
    n = round(settings.window_seconds*rate)
    hop = round(settings.hop_seconds*rate)
    if len(x) < n or not 0 < hop < n or rate/2 <= settings.spectrum_hz[1]:
        raise ValueError('Unsupported analysis support')
    hz, times, z = signal.stft(x, rate, window='hann', nperseg=n,
        noverlap=n-hop, nfft=n, axis=0, boundary=None, padded=False,
        scaling='psd', detrend=False)
    power = abs(z)**2
    lo, hi = np.log2(settings.spectrum_hz)
    grid = np.arange(lo, hi, 1/settings.bins_per_octave)
    frequency = 2**grid
    p = np.empty((len(times), 2, len(grid)))
    for channel in range(2):
        for frame in range(len(times)):
            p[frame, channel] = np.interp(frequency, hz, power[:, channel, frame])
    # Smooth log PSD rather than linear power. Very strong low-frequency
    # components otherwise leak through the broad Gaussian into almost-silent
    # high-frequency bins and dominate shape through its truncated tails.
    db = 10*np.log10(np.maximum(p, 1e-30))
    db = ndimage.gaussian_filter1d(db, settings.smoothing_octaves*settings.bins_per_octave,
                                 axis=-1, mode='reflect')
    # No reference waveform is rewritten. This is an analysis matrix only.
    return frequency, times, db


def hat_basis(x, knots):
    """Linear interpolation weights, including explicit outside-support mask."""
    x = np.asarray(x)
    u = (x-knots[0])/(knots[1]-knots[0])
    left = np.floor(u).astype(int)
    valid = (left >= 0) & (left < len(knots)-1)
    safe = np.clip(left, 0, len(knots)-2)
    w = np.clip(u-safe, 0, 1)
    out = np.zeros(x.shape+(len(knots),))
    np.put_along_axis(out, safe[..., None], (1-w)[..., None], axis=-1)
    np.put_along_axis(out, (safe+1)[..., None], w[..., None], axis=-1)
    return out, valid


def coordinates(frequency, ridge, method):
    fixed = np.broadcast_to(np.log2(frequency), (len(ridge), len(frequency)))
    return [fixed] if method == 'fixed' else [fixed-np.log2(ridge)[:, None]] if method == 'moving' else [fixed, fixed-np.log2(ridge)[:, None]]


def fit(frequency, ridge, db, method, settings=ShapeSettings()):
    if method not in ['fixed', 'moving', 'combined'] or len(ridge) != len(db):
        raise ValueError('Invalid shape input')
    arrays, grids, penalties = [], [], []
    for x in coordinates(frequency, ridge, method):
        knots = x.min()-settings.knot_octaves+np.arange(
            int(np.ceil((x.max()-x.min())/settings.knot_octaves))+4)*settings.knot_octaves
        basis, valid = hat_basis(x, knots)
        assert valid.all()
        # Project nuisance frame offset out before fitting any spectral model.
        basis -= basis.mean(axis=1, keepdims=True)
        arrays.append(basis);grids.append(knots)
        difference = np.diff(np.eye(len(knots)), n=2, axis=0)
        penalties.append(settings.curvature_penalty*difference.T@difference)
    design = np.concatenate(arrays, axis=-1).reshape(-1, sum(len(k) for k in grids))
    y = (db-db.mean(axis=1, keepdims=True)).reshape(-1)
    normal = design.T@design/len(db)
    offset = 0
    for penalty in penalties:
        count = len(penalty)
        normal[offset:offset+count, offset:offset+count] += penalty
        offset += count
    # The constant and combined-model slope allocations are not identifiable.
    # Tiny ridge chooses one numerical representative, not physical layers.
    normal += np.eye(len(normal))*1e-7
    coefficients = np.linalg.solve(normal, design.T@y/len(db))
    return dict(method=method, knots=grids, coefficients=coefficients,
                parameter_count=len(coefficients), settings=asdict(settings))


def predict(model, frequency, ridge):
    features, support = [], np.ones((len(ridge), len(frequency)), dtype=bool)
    for x, knots in zip(coordinates(frequency, ridge, model['method']), model['knots']):
        basis, valid = hat_basis(x, knots)
        features.append(basis);support &= valid
    prediction = np.concatenate(features, axis=-1)@model['coefficients']
    return prediction, support


def future_blocks(times, settings=ShapeSettings()):
    # Past-only training, then an explicit no-overlap gap and disjoint tests.
    first = next((i for i in range(len(times)) if np.sum(times <= times[i]-settings.purge_seconds) >= settings.minimum_train_frames), len(times))
    for start in range(first, len(times)-settings.test_frames+1, settings.test_frames):
        train = np.flatnonzero(times <= times[start]-settings.purge_seconds)
        yield train, np.arange(start, start+settings.test_frames)


def compare(frequency, times, ridge, db, settings=ShapeSettings()):
    if db.shape != (len(times), 2, len(frequency)) or np.any(ridge <= 0):
        raise ValueError('Invalid conditional spectrum matrix')
    folds, errors = [], {m: [[], []] for m in ['fixed', 'moving', 'combined']}
    evaluation = (frequency >= settings.evaluate_hz[0]) & (frequency <= settings.evaluate_hz[1])
    for train, test in future_blocks(times, settings):
        models = {m: [fit(frequency, ridge[train], db[train, c], m, settings) for c in range(2)] for m in errors}
        pred = {m: [predict(model, frequency, ridge[test]) for model in models[m]] for m in errors}
        common = np.broadcast_to(evaluation, (len(test), len(frequency))).copy()
        for variants in pred.values():
            for _, support in variants:
                common &= support
        row = dict(train_indices=train.tolist(), test_indices=test.tolist(),
                   train_seconds=[float(times[train[0]]), float(times[train[-1]])],
                   test_seconds=[float(times[test[0]]), float(times[test[-1]])],
                   centre_gap_seconds=float(times[test[0]]-times[train[-1]]),
                   common_bin_counts=common.sum(axis=1).tolist(),
                   evaluation_bin_count=int(evaluation.sum()),
                   parameter_counts={m: models[m][0]['parameter_count'] for m in models},
                   squared_error_sum={m: [0., 0.] for m in models}, samples_per_channel=0)
        for j, index in enumerate(test):
            mask = common[j]
            if mask.sum() < 20:
                continue
            row['samples_per_channel'] += int(mask.sum())
            for c in range(2):
                actual = db[index, c, mask]
                actual = actual-actual.mean()
                for m in errors:
                    estimate = pred[m][c][0][j, mask]
                    estimate = estimate-estimate.mean()
                    error = (actual-estimate)**2
                    errors[m][c].extend(error.tolist())
                    row['squared_error_sum'][m][c] += float(error.sum())
        if row['samples_per_channel']:
            folds.append(row)
    return dict(status='measured' if folds else 'insufficient_purged_frames', folds=folds,
                spectral_shape_rmse_db_lr={m: [float(np.sqrt(np.mean(e))) if e else None for e in channels] for m, channels in errors.items()},
                compared_spectral_bins_per_channel=len(errors['fixed'][0]),
                meaning='Equal log-frequency-bin RMS log-power shape error after per-frame mean removal on identical supported bins; excludes loudness and phase. Not waveform prediction, source separation, noise fraction or realism.')
