"""Independent periodogram, score and cumulative-cell audit of F3 observations."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--input', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(a.workspace / 'tools' / x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import soundfile as sf
from scipy.signal import periodogram
from drive_evidence_v1.sources import sha


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def independent_features(cells, frequency, settings):
    count = math.ceil(settings['bins_per_octave'] * math.log2(
        settings['grid_stop_hz'] / settings['grid_base_hz'])) + 1
    points = settings['grid_base_hz'] * np.exp2(np.arange(count) / settings['bins_per_octave'])
    values = np.stack([np.interp(points, frequency, cells[:, channel]) for channel in (0, 1)], axis=1)
    values = np.log(np.maximum(values, max(float(np.max(cells)) * 1e-12, np.finfo(float).tiny)))
    radius = round(4 * settings['whitening_sigma_bins'])
    kernel = np.exp(-.5 * (np.arange(-radius, radius + 1) / settings['whitening_sigma_bins']) ** 2)
    kernel /= kernel.sum()
    smooth = np.stack([np.convolve(np.pad(values[:, c], (radius, radius), mode='edge'),
                                  kernel, mode='valid') for c in (0, 1)], axis=1)
    return points, values - smooth


def independent_scores(reference, current, points, settings):
    low, high = settings['comparison_hz']
    indices = np.flatnonzero((points >= low) & (points < high))
    left = reference[indices] - reference[indices].mean(axis=0)
    flat_left = left.ravel().tolist()
    left_square = math.fsum(x * x for x in flat_left)
    scores = []
    for shift in range(settings['minimum_shift'], settings['maximum_shift'] + 1):
        right = current[indices + shift]
        flat_right = (right - right.mean(axis=0)).ravel().tolist()
        denominator = math.sqrt(left_square * math.fsum(x * x for x in flat_right))
        scores.append(math.fsum(x * y for x, y in zip(flat_left, flat_right)) / denominator
                      if denominator > 1e-20 else 0.)
    return scores


def prefix_power(cells, frequency, ratio, bands):
    # Integrate the same cell geometry using an independent prefix integral.
    edges = np.r_[0., frequency + (frequency[1] - frequency[0]) / 2]
    cumulative = np.vstack((np.zeros(2), np.cumsum(cells, axis=0)))
    result = []
    for low, high in bands:
        result.append([np.diff(np.interp([low / ratio, high / ratio], edges, cumulative[:, c]))[0]
                       for c in (0, 1)])
    return np.array(result)


def cumulative_power(cells, frequency, ratio, bands):
    """Integrate boundary cells and sum interior cells without prefix cancellation."""
    edges = np.r_[0., frequency + (frequency[1] - frequency[0]) / 2]
    result = []
    for low, high in bands:
        low, high = low / ratio, high / ratio
        first = max(0, int(np.searchsorted(edges, low, side='right')) - 1)
        stop = min(len(cells), int(np.searchsorted(edges, high, side='left')))
        channel_power = []
        for channel in (0, 1):
            terms = []
            for index in range(first, stop):
                if index == first or index == stop - 1:
                    width = (min(high, edges[index + 1]) - max(low, edges[index])) / (edges[index + 1] - edges[index])
                else:
                    width = 1.
                terms.append(float(cells[index, channel]) * width)
            channel_power.append(math.fsum(terms))
        result.append(channel_power)
    return np.array(result)


a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.acceleration-material-audit/1', result='running', segments=[])
try:
    original = load(a.input / 'report.json')
    assert original['result'] == 'fixed_native_acceleration_observations_complete_not_a_synthesis_profile'
    source = Path(__file__)
    target = a.out / 'exact_sources' / source.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    r.update(source_sha256=sha(source), input_report_sha256=sha(a.input / 'report.json'))
    for name, digest in original['sources'].items():
        assert sha(a.input / 'exact_sources' / name) == digest == sha(repo / name)
    plan = original['plan']; settings = plan['spectral_scale']; bands = plan['bands_hz']
    maxima = dict(cell_power=0., whitened=0., candidate_score=0., band_power=0., colour_db=0., parseval=0.)
    prefix_diagnostic = dict(maximum_colour_difference_db=0.)
    for obs in original['observations']:
        assert sha(a.input / obs['arrays']) == obs['arrays_sha256']
        saved = np.load(a.input / obs['arrays'])
        audio = saved['audio']; n = round(plan['tile_seconds'] * 48000)
        assert len(audio) == n * len(obs['tiles'])
        master = a.workspace / obs['provenance']['master']
        assert sha(master) == obs['provenance']['master_sha256']
        with sf.SoundFile(master) as stream:
            stream.seek(round(obs['provenance']['seconds'][0] * 48000))
            assert stream.samplerate == 48000 and stream.channels == 2
            assert np.array_equal(audio, stream.read(len(audio), dtype='float64', always_2d=True))
        window = np.hanning(n + 1)[:-1]
        recomputed, features = [], []
        for index in range(len(obs['tiles'])):
            tile = audio[index * n:(index + 1) * n]
            f, density = periodogram(tile, fs=48000, window=window, detrend=False,
                                    return_onesided=True, scaling='density', axis=0)
            cells = density * 48000 / n
            assert np.array_equal(f, saved['frequency'])
            maxima['cell_power'] = max(maxima['cell_power'], float(abs(cells - saved['cells'][index]).max()))
            points, feature = independent_features(cells, f, settings)
            maxima['whitened'] = max(maxima['whitened'], float(abs(feature - saved['whitened'][index]).max()))
            for channel in (0, 1):
                energy = math.fsum((float(x) * float(w)) ** 2 for x, w in zip(tile[:, channel], window)) / math.fsum(float(w)**2 for w in window)
                maxima['parseval'] = max(maxima['parseval'], abs(float(cells[:, channel].sum()) - energy))
            recomputed.append(cells); features.append(feature)
        good = []
        for index, row in enumerate(obs['tiles']):
            scores = independent_scores(features[0], features[index], points, settings)
            actual = row['spectral_scale']
            maxima['candidate_score'] = max(maxima['candidate_score'], float(abs(np.array(scores) - actual['candidate_scores']).max()))
            winner = max(range(len(scores)), key=scores.__getitem__)
            shift = winner + settings['minimum_shift']
            assert shift == actual['shift_bins']
            margin = scores[winner] - max(value for k, value in enumerate(scores)
                                          if abs(k - winner) > settings['other_peak_exclusion_bins'])
            supported = (scores[winner] >= settings['minimum_score'] and
                         margin >= settings['minimum_peak_margin'] and
                         winner not in (0, len(scores) - 1))
            assert supported == actual['supported']
            ratio = 2. ** (shift / settings['bins_per_octave'])
            assert ratio == actual['ratio']
            predicted = cumulative_power(recomputed[0], f, ratio, bands)
            measured = cumulative_power(recomputed[index], f, 1., bands)
            maxima['band_power'] = max(maxima['band_power'],
                float(abs(predicted - row['pitch_only_band_power_before_gain_LR']).max()),
                float(abs(measured - row['integrated_band_power_LR']).max()))
            gain = measured.sum(axis=0) / predicted.sum(axis=0)
            colour = 10 * np.log10(np.maximum(measured, 1e-30) / np.maximum(predicted * gain, 1e-30))
            maxima['colour_db'] = max(maxima['colour_db'], float(abs(colour - row['colour_residual_db_LR']).max()))
            old_predicted = prefix_power(recomputed[0], f, ratio, bands)
            old_measured = prefix_power(recomputed[index], f, 1., bands)
            old_gain = old_measured.sum(axis=0) / old_predicted.sum(axis=0)
            old_colour = 10 * np.log10(np.maximum(old_measured, 1e-30) / np.maximum(old_predicted * old_gain, 1e-30))
            error = abs(old_colour - colour)
            if float(error.max()) > prefix_diagnostic['maximum_colour_difference_db']:
                band, channel = np.unravel_index(int(np.argmax(error)), error.shape)
                prefix_diagnostic = dict(maximum_colour_difference_db=float(error.max()),
                    segment=obs['segment'], tile=index, band=bands[band], channel=int(channel),
                    integrated_power=float(measured[band, channel]),
                    prefix_power=float(old_measured[band, channel]),
                    method='Subtraction of two large prefix sums loses relative precision in very weak bands; boundary/interior math.fsum avoids the subtraction')
            assert row['source_center_seconds'] == obs['provenance']['seconds'][0] + (index + .5) * .25
            if supported and index:
                good.append(colour)
        last = obs['tiles'][-1]
        r['segments'].append(dict(segment=obs['segment'], tiles=len(obs['tiles']),
            supported_tiles=sum(row['spectral_scale']['supported'] for row in obs['tiles']),
            last_ratio_candidate=last['spectral_scale']['ratio'], last_ratio_supported=last['spectral_scale']['supported'],
            median_abs_colour_db_over_supported_nonreference_tiles_LR=np.median(abs(np.array(good)), axis=0).tolist(),
            maximum_abs_colour_db_over_supported_nonreference_tiles_LR=np.max(abs(np.array(good)), axis=0).tolist(),
            rejected_centers=[row['source_center_seconds'] for row in obs['tiles'] if not row['spectral_scale']['supported']]))
    r.update(maxima=maxima, original_prefix_integral_diagnostic=prefix_diagnostic)
    assert maxima['cell_power'] < 1e-12 and maxima['whitened'] < 1e-8
    assert maxima['candidate_score'] < 1e-10 and maxima['band_power'] < 1e-12
    assert maxima['colour_db'] < 1e-7 and maxima['parseval'] < 1e-12
    # Extra diagnostic: bound the pitch-only cell approximation on declared
    # synthetic signals. This does not bound real chirp/noise/cabin errors.
    from accel_material_v1.features import compare
    t = np.arange(12000) / 48000
    orders = np.arange(3, 61); freqs = 83.137 * orders
    amp = .05 * orders ** -.7
    def signal(ratio, colour=0.):
        y = np.sum((amp * (freqs / 1500.) ** colour)[:, None] *
                   np.cos(2 * np.pi * freqs[:, None] * ratio * t + .173 * orders[:, None]), axis=0)
        return np.column_stack((y, y * .67))
    base = signal(1.)
    approximation = []
    for shift in [-32, 0, 32, 64]:
        rows, arrays = compare(np.vstack((base, signal(2. ** (shift / 192)))), bands, settings)
        powers = np.array(rows[1]['integrated_band_power_LR'])
        predicted = np.array(rows[1]['pitch_only_band_power_before_gain_LR'])
        occupied = (powers > powers.sum(axis=0) * 1e-6) & (predicted > predicted.sum(axis=0) * 1e-6)
        colour = np.array(rows[1]['colour_residual_db_LR'])
        approximation.append(dict(shift=shift, occupied_bands_LR=occupied.tolist(),
            colour_residual_db_LR=colour.tolist(),
            max_abs_occupied_colour_db=float(abs(colour[occupied]).max())))
    generator = np.random.default_rng(871293)
    noise = generator.standard_normal((24000, 2)) * .01
    negative, _ = compare(noise, bands, settings)
    assert not negative[1]['spectral_scale']['supported']
    r.update(result='all48_native_tiles_and_all7728_scores_independently_verified',
             maxima=maxima, known_pitch_only_approximation=approximation,
             independent_noise_rejected=True,
             interpretation='Finite-window spectral-scale observations; no RPM/load calibration, physical source attribution, new timbre acceptance or synthesis profile')
    print(json.dumps(dict(result=r['result'], maxima=maxima,
        known_approximation_max_db=max(x['max_abs_occupied_colour_db'] for x in approximation))), flush=True)
finally:
    if sys.exc_info()[0]:
        r.update(result='failed', error=repr(sys.exc_info()[1]))
    (a.out / 'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
