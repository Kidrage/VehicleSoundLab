"""Read-only exact-observer frequency split and physical signed error budgets."""
from itertools import combinations
import numpy as np


def locked_rows(audio, weights, amplitude):
    audio = np.asarray(audio)
    size, hop = 4096, 256
    if (audio.ndim != 2 or audio.shape[1] != 2 or len(audio) < size
            or np.iscomplexobj(audio) or not np.isfinite(audio).all()
            or np.shape(weights) != (2049,) or np.any(np.asarray(weights) <= 0)
            or not np.isfinite(weights).all() or not np.isfinite(amplitude) or amplitude <= 0):
        raise ValueError('Complete finite stereo and positive locked metric required')
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    coverage = np.zeros(len(audio))
    for start in range(-3840, len(audio), hop):
        first, stop = max(start, 0), min(start+size, len(audio))
        coverage[first:stop] += window[first-start:stop-start]**2
    starts = np.arange(0, len(audio)-size+1, hop)
    ids = starts[:, None]+np.arange(size)[None]
    endpoint = np.r_[1., np.full(2047, 2.), 1.]
    rows = np.fft.rfft(audio[ids]*window[None, :, None]
        /np.sqrt(coverage[ids, None]), axis=1)
    rows *= (amplitude*np.sqrt(endpoint/size)*weights)[None, :, None]
    conventional = np.fft.rfft(audio[ids]*window[None, :, None], axis=1)
    power = np.mean(abs(conventional)**2, axis=0)*endpoint[:, None]/(size*np.dot(window, window))
    return rows, power, coverage, starts


def virtual_split(target, fitted, weights, amplitude, orders):
    if np.shape(target) != np.shape(fitted) or not np.array_equal(orders, np.arange(1, 289)):
        raise ValueError('Original all288-order target and fitted target required')
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
        weighted_mass_is_not_acoustic_power=True, windows=len(starts))
    highest, above = summary['original_bands'][-1], summary['highest_band_split'][-1]
    summary['above_centre_reference_fraction_of_highest_weighted_mass'] = (
        sum(above['reference_weighted_mass_LR'])/sum(highest['reference_weighted_mass_LR']))
    summary['above_centre_error_fraction_of_highest_weighted_mass'] = (
        sum(above['error_weighted_mass_LR'])/sum(highest['error_weighted_mass_LR']))
    arrays = dict(virtual_frequency=frequency, virtual_band=bands, virtual_split=split,
        virtual_reference_weighted_mass=ref_mass, virtual_error_weighted_mass=err_mass,
        virtual_reference_Welch_FS2=raw_power, virtual_error_Welch_FS2=error_power,
        virtual_coverage=coverage, virtual_starts=starts)
    return arrays, summary


def physical_summary(z):
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    denominator = len(z['starts'])*4096*np.dot(window, window)
    ref = z['band_reference_power']
    autos = z['band_component_auto_power']
    crosses = z['band_component_signed_cross_power']
    return dict(reference_Welch_FS2_LR=(ref/denominator).tolist(),
        component_auto_Welch_FS2_LR=(autos/denominator).tolist(),
        component_signed_cross_Welch_FS2_LR=(crosses/denominator).tolist(),
        total_error_Welch_FS2_LR=(z['band_error_power']/denominator).tolist(),
        combined_component_NRMSE=np.sqrt(autos.sum(axis=2)/ref.sum(axis=1)[:, None]).tolist(),
        combined_total_NRMSE=np.sqrt(z['band_error_power'].sum(axis=1)/ref.sum(axis=1)).tolist(),
        auto_and_signed_cross_powers_are_not_additive_percentages=True)


def sensitivity(variants):
    rows = []
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    endpoint = np.r_[1., np.full(2047, 2.), 1.]
    groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*48000/4096, side='right')
    for (an, a), (bn, b) in combinations(variants, 2):
        assert np.array_equal(a['raw'], b['raw']) and np.array_equal(a['starts'], b['starts'])
        delta = a['components']-b['components']
        ids = a['starts'][:, None]+np.arange(4096)[None]
        X = np.fft.rfft(delta[ids]*window[None, :, None, None], axis=1)
        powers = np.array([np.sum(abs(X[:, groups == band])**2
            *endpoint[None, groups == band, None, None], axis=(0, 1)) for band in range(6)])
        total_delta = a['continuous_OSC']-b['continuous_OSC']
        rows.append(dict(first=an, second=bn,
            combined_component_band_NRMSE_relative_raw=np.sqrt(powers.sum(axis=2)
                /a['band_reference_power'].sum(axis=1)[:, None]).tolist(),
            component_whole_NRMSE_relative_raw=np.sqrt(np.sum(delta**2, axis=(0, 2))
                /np.sum(a['raw']**2)).tolist(),
            continuous_whole_NRMSE_relative_raw=float(np.linalg.norm(total_delta)/np.linalg.norm(a['raw']))))
    return rows
