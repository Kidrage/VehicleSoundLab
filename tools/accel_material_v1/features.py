"""Phase-free spectral-scale observations, separate from engine-clock extraction."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from idle_material_v1.features import spectrum


def grid(settings):
    count = int(np.ceil(settings['bins_per_octave'] * np.log2(
        settings['grid_stop_hz'] / settings['grid_base_hz']))) + 1
    return settings['grid_base_hz'] * 2. ** (np.arange(count) / settings['bins_per_octave'])


def whiten(cells, frequency, settings):
    points = grid(settings)
    # A source-relative floor makes a global amplitude change invariant.
    floor = max(float(np.max(cells)) * 1e-12, np.finfo(float).tiny)
    power = np.column_stack([np.interp(points, frequency, cells[:, channel])
                             for channel in range(2)])
    logged = np.log(np.maximum(power, floor))
    return logged - gaussian_filter1d(logged, settings['whitening_sigma_bins'],
                                     axis=0, mode='nearest')


def scale_match(reference, current, settings):
    points = grid(settings)
    lo, hi = settings['comparison_hz']
    indices = np.flatnonzero((points >= lo) & (points < hi))
    shifts = np.arange(settings['minimum_shift'], settings['maximum_shift'] + 1)
    a = reference[indices].copy()
    a -= a.mean(axis=0)
    scores = []
    for shift in shifts:
        b = current[indices + shift].copy()
        b -= b.mean(axis=0)
        denominator = np.linalg.norm(a) * np.linalg.norm(b)
        scores.append(float(np.sum(a * b) / denominator) if denominator > 1e-20 else 0.)
    scores = np.asarray(scores)
    winner = int(np.argmax(scores))
    separated = abs(shifts - shifts[winner]) > settings['other_peak_exclusion_bins']
    other = float(np.max(scores[separated]))
    margin = float(scores[winner] - other)
    edge = winner in (0, len(shifts) - 1)
    supported = (scores[winner] >= settings['minimum_score'] and
                 margin >= settings['minimum_peak_margin'] and not edge)
    return dict(ratio=float(2. ** (int(shifts[winner]) / settings['bins_per_octave'])),
                shift_bins=int(shifts[winner]), score=float(scores[winner]),
                peak_margin=margin, at_search_edge=edge, supported=bool(supported),
                candidate_scores=scores.tolist())


def shifted_power(cells, frequency, ratio, bands):
    """Conserve native cell power when stretching its frequency intervals."""
    df = frequency[1] - frequency[0]
    left = np.maximum(0., frequency - df / 2)
    right = frequency + df / 2
    width = right - left
    result = []
    for lo, hi in bands:
        overlap = np.maximum(0., np.minimum(right, hi / ratio) -
                             np.maximum(left, lo / ratio)) / width
        result.append(np.sum(cells * overlap[:, None], axis=0))
    return np.array(result)


def compare(audio, bands, settings, rate=48000, tile_frames=12000):
    if len(audio) % tile_frames:
        raise ValueError('Analysis interval must contain only complete fixed tiles')
    tiles = [spectrum(audio[start:start + tile_frames], bands, rate)
             for start in range(0, len(audio), tile_frames)]
    reference = tiles[0]
    reference_feature = whiten(reference['cells'], reference['frequency'], settings)
    rows, features = [], []
    for index, tile in enumerate(tiles):
        feature = whiten(tile['cells'], tile['frequency'], settings)
        match = scale_match(reference_feature, feature, settings)
        predicted = shifted_power(reference['cells'], reference['frequency'],
                                  match['ratio'], bands)
        # Use the same fractional cell integration for both sides. This differs
        # from a centre-bin band sum at edges; keep the original sum separately.
        observed = shifted_power(tile['cells'], tile['frequency'], 1., bands)
        gain = observed.sum(axis=0) / np.maximum(predicted.sum(axis=0), 1e-30)
        residual = 10 * np.log10(np.maximum(observed, 1e-30) /
                                 np.maximum(predicted * gain, 1e-30))
        rows.append(dict(tile=index, relative_center_seconds=(index + .5) * tile_frames / rate,
                         spectral_scale=match, measured_cell_band_power_LR=tile['power'].tolist(),
                         integrated_band_power_LR=observed.tolist(),
                         pitch_only_band_power_before_gain_LR=predicted.tolist(),
                         global_power_gain_LR=gain.tolist(),
                         colour_residual_db_LR=residual.tolist(),
                         parseval_error=tile['parseval_error']))
        features.append(feature)
    return rows, dict(cells=np.array([tile['cells'] for tile in tiles]),
                      frequency=reference['frequency'], whitened=np.array(features))
