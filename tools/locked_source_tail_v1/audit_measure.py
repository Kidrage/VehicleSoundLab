"""Independent declared FP64 observer on saved waveforms, and signed LR Grams."""
import numpy as np


LABELS = ['0_3k', '3_6k', '6_8k', '8_10k', '10_14k', '14k_plus',
          '14_16k', '16_18432', 'centre18432', 'above18432']


def masks():
    f = np.arange(2049)*16
    return [(f >= lo) & (f < hi) for lo, hi in
        ((0, 3000), (3000, 6000), (6000, 8000), (8000, 10000),
         (10000, 14000), (14000, 32769), (14000, 16000),
         (16000, 18432), (18432, 18433), (18433, 32769))]


def observe(audio, weights, amplitude):
    n = len(audio)
    w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    coverage = np.zeros(n)
    all_starts = range(-3840, n, 256)
    for first in all_starts:
        lo, hi = max(0, first), min(n, first+4096)
        coverage[lo:hi] += w[lo-first:hi-first]**2
    inv = 1/np.sqrt(coverage)
    edge = np.full(2049, np.sqrt(2.)); edge[[0, -1]] = 1
    rows, ordinary = [], []
    for first in all_starts:
        if first < 0 or first+4096 > n:
            continue
        part = audio[first:first+4096]*inv[first:first+4096, None]
        part *= w[:, None]
        rows.append(np.column_stack([np.fft.rfft(part[:, c])*edge/64 for c in (0, 1)]))
        ordinary.append(audio[first:first+4096]*w[:, None])
    rows = np.asarray(rows)*amplitude*weights[None, :, None]
    ordinary = np.fft.rfft(np.asarray(ordinary), axis=1)
    endpoints = np.r_[1., np.full(2047, 2.), 1.]
    power = np.mean(abs(ordinary)**2, axis=0)*endpoints[:, None]/(4096*np.dot(w, w))
    return rows, power


def compare_positive(got, expected, gate=2e-12):
    got, expected = np.asarray(got), np.asarray(expected)
    assert got.shape == expected.shape and np.isfinite(got).all() and np.isfinite(expected).all()
    scale = np.maximum(abs(got), abs(expected))
    error = np.divide(abs(got-expected), scale, out=np.zeros_like(scale, dtype=float), where=scale>0)
    value = float(error.max()) if error.size else 0.
    assert value < gate, ('relative', value, gate)
    return value


def verify(values, stored, report, weights, amplitude):
    bands = masks()
    reference = report['diagnostic_reference']
    observed = {name: observe(audio[2048:-2048], weights, amplitude) for name, audio in values.items()}
    R = observed[reference][0]
    checks, grams = {}, {}
    for name, (X, power) in observed.items():
        mass = np.sum(abs(X)**2, axis=0)
        checks[name+'_all2049_LR_mass'] = compare_positive(stored[name+'_weighted_mass'], mass)
        checks[name+'_all2049_LR_Welch'] = compare_positive(stored[name+'_Welch_FS2'], power)
        T, tp = observe((values[name]-values[reference])[2048:-2048], weights, amplitude)
        tm = np.sum(abs(T)**2, axis=0)
        checks[name+'_time_residual_all_mass'] = compare_positive(stored[name+'_time_difference_weighted_mass'], tm)
        checks[name+'_time_residual_all_Welch'] = compare_positive(stored[name+'_time_difference_Welch_FS2'], tp)
        D = X-R
        for label, mask in zip(LABELS, bands):
            signal_report = report['signals'][name][label]
            checks[name+'_'+label+'_signal_mass'] = compare_positive(signal_report['weighted_mass_LR'], mass[mask].sum(axis=0))
            checks[name+'_'+label+'_signal_Welch'] = compare_positive(signal_report['Welch_FS2_LR'], power[mask].sum(axis=0))
            V = np.concatenate((R[:, mask], D[:, mask]), axis=2).reshape(-1, 4)
            G = np.empty((4, 4), complex)
            for i in range(4):
                for j in range(4):
                    G[i, j] = np.sum(V[:, i]*V[:, j].conj())
            saved = stored[name+'_vs_reference_'+label+'_Gram']
            scale = np.sqrt(np.maximum(0, np.diag(G).real[:, None]*np.diag(G).real[None]))
            delta = abs(saved-G)
            assert not np.count_nonzero(delta[scale == 0])
            error = float(np.max(np.divide(delta, scale, out=np.zeros_like(scale), where=scale>0)))
            assert error < 2e-12, (name, label, 'all_signed_Gram', error)
            grams[name+'_'+label] = error
            a, d = np.diag(G).real[:2], np.diag(G).real[2:]
            cross = 2*np.array([G[c, c+2].real for c in (0, 1)])
            total = np.sum(abs(X[:, mask])**2, axis=(0, 1))
            group = report['comparisons'][name]['groups'][label]
            for key, value in (('reference_mass_LR', a), ('difference_mass_LR', d), ('candidate_mass_LR', total)):
                checks[name+'_'+label+'_'+key] = compare_positive(group[key], value)
            denominator = a+d+abs(cross)
            e = abs(np.asarray(group['signed_cross_mass_LR'])-cross)
            assert np.max(np.divide(e, denominator, out=np.zeros_like(e), where=denominator>0)) < 2e-12
            closure = np.divide(abs(total-a-d-cross), denominator, out=np.zeros_like(e), where=denominator>0)
            assert max(float(np.max(closure)), group['signed_power_closure_relative']) < 2e-12
            for key, value in (('transform_difference_NRMSE', np.sqrt(d.sum()/a.sum()) if a.sum() else None),
                               ('time_difference_NRMSE', np.sqrt(tm[mask].sum()/a.sum()) if a.sum() else None)):
                if value is None:
                    assert group[key] is None
                else:
                    checks[name+'_'+label+'_'+key] = compare_positive(group[key], value)
        delta = values[name]-values[reference]
        for key, value in (('time_max_FS', np.max(abs(delta))),
                           ('time_NRMSE', np.linalg.norm(delta)/np.linalg.norm(values[reference]))):
            checks[name+'_'+key] = compare_positive(report['comparisons'][name][key], value)
    return dict(checks=checks, Gram_checks=grams, all2049bins_all_supported_windows_both_channels=True,
        independently_verified_saved_wave_spectra_not_cross_operator_bound=True)
