"""One shared integer-lag match followed by fixed-lag spectral/detail checks."""
import math
import numpy as np
from scipy.signal import correlate, butter, sosfiltfilt


def coefficient(first, second):
    one = first-first.mean(axis=0, keepdims=True)
    two = second-second.mean(axis=0, keepdims=True)
    denominator = np.sqrt(np.sum(one*one)*np.sum(two*two))
    return float(np.sum(one*two)/denominator) if denominator > 0 else 0.


def match(template, search, rate, nominal_offset):
    frames = len(template)
    if search.shape[1] != 2 or template.shape[1] != 2 or len(search) < frames:
        raise ValueError('Native stereo template and sufficient search context required')
    centered = template-template.mean(axis=0, keepdims=True)
    dot = np.zeros(len(search)-frames+1)
    energy = np.zeros_like(dot)
    for channel in range(2):
        values = search[:, channel]
        dot += correlate(values, centered[:, channel], mode='valid', method='fft')
        cumulative = np.r_[0., np.cumsum(values)]
        square = np.r_[0., np.cumsum(values*values)]
        sums = cumulative[frames:]-cumulative[:-frames]
        energy += square[frames:]-square[:-frames]-sums*sums/frames
    denominator = np.sqrt(np.maximum(energy, 0)*np.sum(centered*centered))
    ncc = np.divide(dot, denominator, out=np.zeros_like(dot), where=denominator > 0)
    index = int(np.argmax(abs(ncc)))
    aligned = search[index:index+frames]
    direct = coefficient(template, aligned)
    scalar_dot = math.fsum(float(x*y) for x, y in zip(centered.ravel(),
        (aligned-aligned.mean(axis=0, keepdims=True)).ravel()))
    scalar = scalar_dot/np.sqrt(float(np.sum(centered*centered))*
        float(np.sum((aligned-aligned.mean(axis=0, keepdims=True))**2)))
    error = float(max(abs(direct-ncc[index]), abs(scalar-direct)))
    rows = []
    residuals = []
    for channel in range(2):
        x, y = template[:, channel], aligned[:, channel]
        one, two = x-x.mean(), y-y.mean()
        gain = float(one@two/(one@one))
        offset = float(y.mean()-gain*x.mean())
        residual = y-(gain*x+offset)
        relative = float(np.linalg.norm(residual)/np.linalg.norm(two))
        residuals.append(relative)
        rows.append(dict(channel=channel, gain=gain, DC_offset=offset,
                         normalized_affine_residual=relative, raw_NCC=coefficient(x[:, None], y[:, None])))
    blocks = [dict(first_sample=start, samples=rate,
        joint_NCC=coefficient(template[start:start+rate], aligned[start:start+rate]))
        for start in range(0, frames-rate+1, rate)]
    bands = []
    for low, high in ((3000, 6000), (6000, 14000)):
        sos = butter(4, (low, high), 'bandpass', fs=rate, output='sos')
        # Filter full search context once, then select the same integer lag.
        first = sosfiltfilt(sos, template, axis=0)
        second = sosfiltfilt(sos, search, axis=0)[index:index+frames]
        margin = round(.05*rate)
        bands.append(dict(band_Hz=[low, high], edge_margin_seconds=.05,
            fixed_lag_joint_NCC=coefficient(first[margin:-margin], second[margin:-margin])))
    result = dict(selected_search_sample=index, integer_lag_samples=index-nominal_offset,
        integer_lag_seconds=(index-nominal_offset)/rate, joint_NCC=direct,
        FFT_vs_direct_vs_scalar_maximum_error=error, channels=rows,
        maximum_normalized_affine_residual=max(residuals), contiguous_blocks=blocks,
        fixed_lag_high_bands=bands, independent_take_established=False)
    return result, dict(aligned_second=aligned, candidate_NCC=ncc,
                         lag_seconds=(np.arange(len(ncc))-nominal_offset)/rate)


def passes(result, gates):
    return bool(abs(result['joint_NCC']) >= gates['joint_absolute_NCC']
        and min(abs(row['joint_NCC']) for row in result['contiguous_blocks']) >= gates['minimum_block_absolute_NCC']
        and min(abs(row['fixed_lag_joint_NCC']) for row in result['fixed_lag_high_bands']) >= gates['minimum_high_band_absolute_NCC']
        and result['maximum_normalized_affine_residual'] <= gates['maximum_affine_normalized_residual'])
