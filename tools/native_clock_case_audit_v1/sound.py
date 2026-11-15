"""Independent Welch/CSD/MS operator and frozen-series statistics audit."""
import math
import numpy as np
from scipy import signal, fft


def extent(value):
    value = np.asarray(value)
    return float(np.max(abs(value))) if value.size else 0.


def aggregates(power, cross, mid_side):
    n = len(power)
    mean = np.array([[math.fsum(power[:, b, c]) / n for c in (0, 1)] for b in range(6)])
    centered = power.reshape(n, 12) - mean.reshape(1, 12)
    covariance = sum(np.outer(row, row) for row in centered) / n
    cv = np.zeros((6, 2))
    good = mean > 0
    cv[good] = np.sqrt(np.diag(covariance)).reshape(6, 2)[good] / mean[good]
    coherence = np.zeros(6, complex)
    den = np.sqrt(mean[:, 0]) * np.sqrt(mean[:, 1])
    for b in range(6):
        if den[b] > 0:
            value = complex(math.fsum(cross[:, b].real), math.fsum(cross[:, b].imag)) / n
            coherence[b] = value / den[b]
    lagged = []
    for lag in range(1, min(9, n)):
        lagged.append(sum(np.outer(centered[i], centered[i + lag]) for i in range(n - lag)) / (n - lag))
    return dict(mean_power=mean, power_defined=good, CV=cv, covariance=covariance,
        lag_covariance=np.asarray(lagged) if lagged else np.empty((0, 12, 12)),
        complex_coherence=coherence, coherence_defined=den > 0,
        mean_mid_side=np.array([[math.fsum(mid_side[:, b, c]) / n for c in (0, 1)] for b in range(6)]))


def verify(name, audio, saved, check, gates):
    N, hop, rate = 4096, 256, 48000
    starts = np.arange(0, len(audio) - N + 1, hop)
    raw = np.array([audio[s:s + N] for s in starts])
    # Match the declared observed Hann vector, including its FP64 values.
    # scipy.windows.hann constructs mathematically equal but different last
    # bits; a different observation operator is not a valid ratio audit.
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(N) / N)
    kwargs = dict(fs=rate, window=window, nperseg=N, noverlap=0, detrend=False,
                  scaling='density', axis=1)
    frequency, psd = signal.welch(raw, **kwargs)
    _, cross = signal.csd(raw[:, :, 1], raw[:, :, 0], **kwargs)
    ms = np.stack(((raw[:, :, 0] + raw[:, :, 1]) / 2,
                   (raw[:, :, 0] - raw[:, :, 1]) / 2), axis=-1)
    _, ms_psd = signal.welch(ms, **kwargs)
    groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], frequency, side='right')
    df = rate / N
    powers = np.stack([psd[:, groups == b].sum(axis=1) * df for b in range(6)], axis=1)
    C = np.stack([cross[:, groups == b].sum(axis=1) * df for b in range(6)], axis=1)
    MS = np.stack([ms_psd[:, groups == b].sum(axis=1) * df for b in range(6)], axis=1)
    get = lambda key: saved[name + '_' + key]
    assert np.array_equal(get('starts'), starts) and np.array_equal(get('frequency'), frequency)
    assert np.array_equal(get('bin_bands'), groups)
    scale = extent(powers)
    g = gates['independent_linear_spectral_relative_total_power_max']
    check(name + '_independent_linear_power', get('broad_power'), powers, scale, g)
    check(name + '_independent_linear_cross', get('broad_Gram')[:, :, 0, 1], C, scale, g)
    check(name + '_independent_direct_MS', get('broad_mid_side'), MS, scale, g)
    gram = np.zeros((len(starts), 6, 2, 2), complex)
    gram[:, :, 0, 0], gram[:, :, 1, 1] = powers[:, :, 0], powers[:, :, 1]
    gram[:, :, 0, 1], gram[:, :, 1, 0] = C, C.conj()
    check(name + '_independent_band_Gram', get('broad_Gram'), gram, scale, g)
    check(name + '_independent_full_Gram', get('full_Gram'), gram.sum(axis=1), 6 * scale, g)
    weighted = raw * window[None, :, None]
    time = np.zeros((len(starts), 2, 2))
    for c in (0, 1):
        for d in (0, 1):
            time[:, c, d] = (weighted[:, :, c] * weighted[:, :, d]).sum(axis=1) / np.dot(window, window)
    check(name + '_independent_time_Gram', get('windowed_time_Gram'), time, 6 * scale, g)
    # Normalized checks use the same frozen observed linear series. This does
    # not relabel the five retained cross-FFT tiny-line failures as passes.
    expected = aggregates(get('broad_power'), get('broad_Gram')[:, :, 0, 1], get('broad_mid_side'))
    g = gates['frozen_statistics_relative_nonzero_field_max']
    for field, value in expected.items():
        actual = get('broad_' + field)
        if value.dtype == bool:
            assert np.array_equal(actual, value)
        else:
            check(name + '_frozen_' + field, actual, value, extent(value), g)
    eps = np.finfo(float).eps
    gamma = 32 * N * eps / (1 - 32 * N * eps)
    E = gamma * np.sum(abs(weighted), axis=1)
    weights = np.full(N // 2 + 1, 2 / (N * np.dot(window, window)))
    weights[[0, -1]] /= 2
    uncertainty, cross_uncertainty = [], []
    for b in range(6):
        e = E * math.sqrt(math.fsum(weights[groups == b]))
        root = np.sqrt(get('broad_power')[:, b])
        uncertainty.append(2 * root * e + e * e)
        cross_uncertainty.append(root[:, 0] * e[:, 1] + root[:, 1] * e[:, 0] + e[:, 0] * e[:, 1])
    P = np.stack(uncertainty, axis=1)
    X = np.stack(cross_uncertainty, axis=1)
    mean = get('broad_mean_power')
    error = P.mean(axis=0)
    relative = np.zeros_like(mean)
    np.divide(error, mean, out=relative, where=mean > 0)
    sensitivity = dict(power_uncertainty=P, cross_uncertainty=X, mean_power_uncertainty=error,
        power_lower_margin=mean - error, power_relative_uncertainty=relative,
        power_resolution_defined=mean > 0, power_resolved=mean > error,
        coherence_resolved=(mean > error).all(axis=1), FFT_absolute_sensitivity=E,
        roundoff_gamma=np.array(gamma), sensitivity_is_certified_bound=np.array(False))
    for field, value in sensitivity.items():
        key = field if field in ('FFT_absolute_sensitivity', 'roundoff_gamma', 'sensitivity_is_certified_bound') else field
        actual = get('broad_' + key)
        if value.dtype == bool:
            assert np.array_equal(actual, value)
        else:
            check(name + '_engineering_sensitivity_' + field, actual, value, extent(value), g)
    return len(starts)


def normalized(error, reference):
    numerator = float(np.sum(abs(error) ** 2))
    denominator = float(np.sum(abs(reference) ** 2))
    if denominator:
        return math.sqrt(numerator / denominator)
    return 0. if numerator == 0 else None


def comparisons(candidate_name, reference_name, saved, result, check, gates):
    get = lambda which, key: saved[which + '_' + key]
    audio, reference = get(candidate_name, 'audio'), get(reference_name, 'audio')
    delta = audio - reference
    expected = dict(wave_NRMSE=normalized(delta, reference),
        channel_wave_NRMSE=[normalized(delta[:, c], reference[:, c]) for c in (0, 1)],
        signed_mean_FS=delta.mean(axis=0).tolist(),
        signed_peak_range_FS=[delta.min(axis=0).tolist(), delta.max(axis=0).tolist()])
    size = 4096
    starts = np.arange(0, len(reference) - size + 1, 256)
    w = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    index = starts[:, None] + np.arange(size)[None, :]
    ref = fft.rfft(reference[index] * w[None, :, None], axis=1)
    diff = fft.rfft(delta[index] * w[None, :, None], axis=1)
    ids = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.fft.rfftfreq(size, 1 / 48000), side='right')
    weights = np.full(size // 2 + 1, 2.)
    weights[[0, -1]] = 1
    expected['band_complex_NRMSE'] = [normalized(diff[:, ids == b] * np.sqrt(weights[ids == b])[None, :, None],
        ref[:, ids == b] * np.sqrt(weights[ids == b])[None, :, None]) for b in range(6)]
    label = candidate_name + '_vs_' + reference_name
    g = gates['frozen_statistics_relative_nonzero_field_max']

    def mixed(field, observed, wanted, scale=1.):
        left, right = np.asarray(observed, object), np.asarray(wanted, object)
        # JSON [] cannot retain the trailing12x12 shape of a zero-length lag
        # series. Admit exactly that existing serialization, not missing data.
        if field == 'lag_covariance_signed_change_FS4' and right.shape == (0, 12, 12):
            assert left.shape == (0,)
            return
        assert left.shape == right.shape, (field, left.shape, right.shape)
        for x, y in zip(left.ravel(), right.ravel()):
            if x is None or y is None:
                assert x is y, (field, x, y)
            else:
                check(label + '_' + field, x, y, scale, g)

    for field, value in expected.items():
        scale = max(extent(audio), extent(reference)) if field.startswith('signed_') else max(1., extent([x for x in np.asarray(value, object).ravel() if x is not None]))
        mixed(field, result[field], value, scale)
    changes = result['signed_changes']['broad']
    assert set(result['signed_changes']) == {'broad'}
    for field, title in (('mean_power', 'power'), ('mean_mid_side', 'mid_side')):
        left, right = get(candidate_name, 'broad_' + field), get(reference_name, 'broad_' + field)
        mixed(title + '_change_FS2', changes[title + '_change_FS2'], left - right, max(extent(left), extent(right)))
        db = [[float(10 * np.log10(x / y)) if x > 0 and y > 0 else None
               for x, y in zip(a, b)] for a, b in zip(left, right)]
        mixed(title + '_change_dB', changes[title + '_change_dB'], db)
    for field in ('CV', 'complex_coherence'):
        maskfield = 'power_defined' if field == 'CV' else 'coherence_defined'
        mask = get(candidate_name, 'broad_' + maskfield) & get(reference_name, 'broad_' + maskfield)
        left, right = get(candidate_name, 'broad_' + field), get(reference_name, 'broad_' + field)
        diff = left - right
        wanted = (np.where(mask, diff, None).tolist() if field == 'CV' else
                  [[float(v.real), float(v.imag)] if good else None for v, good in zip(diff, mask)])
        # Complex entries include pairs while undefined values remain None.
        if field == 'CV':
            mixed(field + '_change', changes[field + '_change'], wanted, max(extent(left), extent(right)))
        else:
            assert len(changes[field + '_change']) == len(wanted)
            for x, y in zip(changes[field + '_change'], wanted):
                if y is None:
                    assert x is None
                else:
                    mixed(field + '_change', x, y, max(extent(left), extent(right)))
    for field in ('covariance', 'lag_covariance'):
        left, right = get(candidate_name, 'broad_' + field), get(reference_name, 'broad_' + field)
        diff = left - right
        mixed(field + '_signed_change_FS4', changes[field + '_signed_change_FS4'], diff, max(extent(left), extent(right)))
        denominator = float(np.linalg.norm(right))
        wanted = float(np.linalg.norm(diff) / denominator) if denominator else None
        mixed(field + '_relative_difference', changes[field + '_relative_difference'], wanted)
    return expected
