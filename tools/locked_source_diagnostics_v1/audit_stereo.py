"""Independent direct stereo observations and frozen-series aggregation."""
import numpy as np
from scipy import signal
from native_clock_case_audit_v1.sound import aggregates


def verify(label, audio, saved, orders, check):
    size, rate, hop = 4096, 65536, 256
    starts = np.arange(0, len(audio)-size+1, hop)
    raw = np.array([audio[first:first+size] for first in starts])
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    options = dict(fs=rate, window=window, nperseg=size, noverlap=0, detrend=False, scaling='density', axis=1)
    frequency, psd = signal.welch(raw, **options)
    _, cross = signal.csd(raw[:, :, 1], raw[:, :, 0], **options)
    ms_audio = np.stack(((raw[:, :, 0]+raw[:, :, 1])/2, (raw[:, :, 0]-raw[:, :, 1])/2), axis=-1)
    _, ms_psd = signal.welch(ms_audio, **options)
    groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], frequency, side='right')
    line_bins = (4*orders).astype(int)
    line_groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], 64*orders, side='right')
    get = lambda key: saved[label+'_'+key]
    assert np.array_equal(get('starts'), starts) and np.array_equal(get('frequency'), frequency)
    assert np.array_equal(get('bin_bands'), groups)
    series = {}
    for prefix in ('broad', 'line'):
        masks = [groups == band for band in range(6)] if prefix == 'broad' else [line_bins[line_groups == band] for band in range(6)]
        multiplier = rate/size if prefix == 'broad' else rate*np.dot(window, window)/window.sum()**2
        power = np.stack([psd[:, mask].sum(axis=1)*multiplier for mask in masks], axis=1)
        correlation = np.stack([cross[:, mask].sum(axis=1)*multiplier for mask in masks], axis=1)
        mid_side = np.stack([ms_psd[:, mask].sum(axis=1)*multiplier for mask in masks], axis=1)
        gram = np.zeros((len(starts), 6, 2, 2), complex)
        gram[:, :, 0, 0], gram[:, :, 1, 1] = power[:, :, 0], power[:, :, 1]
        gram[:, :, 0, 1], gram[:, :, 1, 0] = correlation, correlation.conj()
        scale = float(np.max(abs(power)))
        for field, expected in (('power', power), ('Gram', gram), ('mid_side', mid_side)):
            check(label+'_'+prefix+'_direct_'+field, get(prefix+'_'+field), expected, scale)
        # Same frozen observed series avoids equating distinct rounded FFTs.
        expected = aggregates(get(prefix+'_power'), get(prefix+'_Gram')[:, :, 0, 1], get(prefix+'_mid_side'))
        for field, value in expected.items():
            actual = get(prefix+'_'+field)
            if value.dtype == bool: assert np.array_equal(actual, value)
            else:
                scale = float(np.max(abs(value))) if value.size else 0.
                check(label+'_'+prefix+'_frozen_'+field, actual, value, scale)
        series[prefix] = gram
    scale = float(np.max(abs(series['broad'])))
    check(label+'_direct_full_Gram', get('full_Gram'), series['broad'].sum(axis=1), 6*scale)
    weighted = raw*window[None, :, None]
    time_gram = np.empty((len(starts), 2, 2))
    for left in (0, 1):
        for right in (0, 1):
            time_gram[:, left, right] = (weighted[:, :, left]*weighted[:, :, right]).sum(axis=1)/np.dot(window, window)
    check(label+'_direct_time_Gram', get('windowed_time_Gram'), time_gram, 6*scale)
    return dict(windows=len(starts), direct_broad_and_line_Gram=True, direct_mid_side=True,
        direct_time_Gram=True, frozen_joint_statistics=True,
        legacy_cross_FFT_normalized_failures_not_relabelled=True)
