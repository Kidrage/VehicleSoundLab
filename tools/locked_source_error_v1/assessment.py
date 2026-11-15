"""Use the already qualified declared saved-wave observer, not a new FFT law.

The old assessment multiplied Hann before division. That is a different FP64
operator at almost empty bins. Keep its history immutable and explicitly use
the declared new-source measurement order here. Physical summaries are shared.
"""
import numpy as np
from locked_source_guard_v1.measurement import frame


def locked_rows(audio, weights, amplitude):
    audio, weights = np.asarray(audio), np.asarray(weights)
    if (weights.shape != (2049,) or np.iscomplexobj(weights)
            or not np.isfinite(weights).all() or np.any(weights <= 0)
            or not np.isfinite(amplitude) or amplitude <= 0):
        raise ValueError('Original finite positive locked observer required')
    rows, coverage = frame(audio)
    all_starts = np.arange(-3840, len(audio), 256)
    keep = (all_starts >= 0) & (all_starts+4096 <= len(audio))
    starts = all_starts[keep]
    rows = rows[keep]*amplitude*weights[None, :, None]
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    endpoint = np.r_[1., np.full(2047, 2.), 1.]
    ids = starts[:, None]+np.arange(4096)[None]
    ordinary = np.fft.rfft(audio[ids]*window[None, :, None], axis=1)
    power = np.mean(abs(ordinary)**2, axis=0)*endpoint[:, None]/(4096*np.dot(window, window))
    return rows, power, coverage, starts


def virtual_split(target, fitted, weights, amplitude, orders):
    if np.shape(target) != np.shape(fitted) or not np.array_equal(orders, np.arange(1, 289)):
        raise ValueError('Complete original288-order target and fitted waveform required')
    reference, raw_power, coverage, starts = locked_rows(target, weights, amplitude)
    delta, error_power, other_coverage, other_starts = locked_rows(fitted-target, weights, amplitude)
    assert np.array_equal(coverage, other_coverage) and np.array_equal(starts, other_starts)
    frequency = np.arange(2049)*16.
    bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], frequency, side='right')
    split = np.full(2049, -1, dtype=int)
    split[(frequency >= 14000) & (frequency < 16000)] = 0
    split[(frequency >= 16000) & (frequency < 18432)] = 1
    split[frequency == 18432] = 2
    split[frequency > 18432] = 3
    ref_mass = np.sum(abs(reference)**2, axis=0)
    err_mass = np.sum(abs(delta)**2, axis=0)

    def group(mask):
        rp, ep = ref_mass[mask].sum(axis=0), err_mass[mask].sum(axis=0)
        return dict(bins=int(np.count_nonzero(mask)), reference_weighted_mass_LR=rp.tolist(),
            error_weighted_mass_LR=ep.tolist(),
            combined_complex_NRMSE=float(np.sqrt(ep.sum()/rp.sum())) if rp.sum() else None,
            reference_Welch_FS2_LR=raw_power[mask].sum(axis=0).tolist(),
            error_Welch_FS2_LR=error_power[mask].sum(axis=0).tolist())
    summary = dict(original_bands=[group(bands == b) for b in range(6)],
        highest_band_split=[dict(name=name, **group(split == j)) for j, name in enumerate(
            ('14-16k', '16-18.432k_exclusive', '18.432k_centre', 'strictly_above_18.432k'))],
        virtual_rate=65536, maximum_carrier_centre_Hz=18432,
        maximum_carrier_centre_is_not_strict_bandwidth=True,
        weighted_mass_is_not_acoustic_power=True, windows=len(starts),
        observer='verified saved-wave declared FP64 order, original weights and amplitude')
    highest, above = summary['original_bands'][-1], summary['highest_band_split'][-1]
    for name in ('reference', 'error'):
        key = name+'_weighted_mass_LR'
        summary['above_centre_'+name+'_fraction_of_highest_weighted_mass'] = sum(above[key])/sum(highest[key])
    arrays = dict(virtual_frequency=frequency, virtual_band=bands, virtual_split=split,
        virtual_reference_weighted_mass=ref_mass, virtual_error_weighted_mass=err_mass,
        virtual_reference_Welch_FS2=raw_power, virtual_error_Welch_FS2=error_power,
        virtual_coverage=coverage, virtual_starts=starts)
    return arrays, summary
