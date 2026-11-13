"""Independent native periodograms, scanned peaks, descriptors and all48 graphs."""
import argparse
import math
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
from scipy.signal import periodogram
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_audit.py')
r = dict(result='running', windows=0, peak_observations=0, graphs=0,
         maximum_power_error=0., maximum_descriptor_error=0., maximum_peak_error=0., summaries=[])

def near(x, y, tol=1e-10):
    error = float(abs(np.asarray(x) - np.asarray(y)).max(initial=0))
    assert error <= tol, (error, tol)
    return error

def power_of(audio):
    window = np.array([.5 - .5 * math.cos(2 * math.pi * i / len(audio)) for i in range(len(audio))])
    hz, density = periodogram(audio, 48000, window, detrend=False, axis=0)
    return hz, density * (48000 / len(audio))

def verify_stats(hz, power, row, bands):
    total = np.array([math.fsum(power[:, c]) for c in range(2)])
    r['maximum_power_error'] = max(r['maximum_power_error'], near(total, row['total_power_LR']))
    for k, (lo, hi) in enumerate(bands):
        indices = [i for i, f in enumerate(hz) if lo <= f < hi]
        values = power[indices]
        sums = np.array([math.fsum(values[:, c]) for c in range(2)])
        r['maximum_power_error'] = max(r['maximum_power_error'], near(sums, row['band_power_LR'][k]))
        fraction = np.divide(sums, total, out=np.zeros(2), where=total > 0)
        near(fraction, row['band_fraction_of_full_native_LR'][k])
        for c in range(2):
            actual = row['descriptors'][k][c]
            if not indices or sums[c] == 0:
                assert actual is None
                continue
            array = [float(v) for v in values[:, c]]
            flatness = math.exp(math.fsum(math.log(max(v, np.finfo(float).tiny)) for v in array) / len(array)) / (sums[c] / len(array))
            concentration = max(math.fsum(array[max(0, i - 1):min(len(array), i + 2)]) for i in range(len(array))) / sums[c]
            near(hz[indices[max(range(len(array)), key=array.__getitem__)]], actual['maximum_cell_hz'])
            r['maximum_descriptor_error'] = max(r['maximum_descriptor_error'], near(flatness, actual['flatness']),
                near(concentration, actual['maximum_three_cell_fraction']))

def native_inventory(power):
    total = power.sum(axis=1)
    logs = 10 * np.log10(np.maximum(total, np.finfo(float).tiny))
    # Native4Hz cells + original round(6/4)=2 spacing: distinct local maxima
    # are already at least2cells apart, including plateau midpoints.
    peaks = []
    i = 1
    while i < len(logs) - 1:
        end = i
        while end < len(logs) - 1 and logs[end + 1] == logs[i]:
            end += 1
        if logs[i] > logs[i - 1] and end < len(logs) - 1 and logs[end] > logs[end + 1]:
            peaks.append((i + end) // 2)
        i = end + 1
    assert all(y - x >= 2 for x, y in zip(peaks, peaks[1:]))
    maximum = max((float(v) for i, v in enumerate(total) if 30 <= i * 4 < 200), default=0)
    chosen, prominence, frequencies = [], [], []
    for index in peaks:
        if not 30 <= index * 4 < 200 or total[index] < maximum * 10 ** (-42 / 10):
            continue
        left = right = float(logs[index])
        j = index - 1
        while j >= 0 and logs[j] <= logs[index]:
            left = min(left, float(logs[j]))
            j -= 1
        j = index + 1
        while j < len(logs) and logs[j] <= logs[index]:
            right = min(right, float(logs[j]))
            j += 1
        prom = logs[index] - max(left, right)
        if prom < 8:
            continue
        denominator = logs[index - 1] - 2 * logs[index] + logs[index + 1]
        delta = .5 * (logs[index - 1] - logs[index + 1]) / denominator if denominator else 0
        chosen.append(index)
        prominence.append(float(prom))
        frequencies.append(float((index + max(-.5, min(.5, delta))) * 4))
    return chosen, frequencies, prominence

def verify_inventory(power, actual):
    indices, hz, prominence = native_inventory(power)
    assert actual['bin'] == indices and actual['native_bin_hz'] == 4
    r['maximum_peak_error'] = max(r['maximum_peak_error'], near(hz, actual['hz'], 1e-8),
        near(prominence, actual['prominence_db'], 1e-7), near(power[indices], actual['power_LR']))
    r['peak_observations'] += len(indices)

def graph(refs, observed, ratio, actual):
    edges = []
    expected, radii = [], []
    for f in refs:
        center = f * ratio
        radius = 4 * (1 + ratio) + center * (2 ** (.5 / 192) - 1)
        expected.append(center)
        radii.append(radius)
        edges.append([int(abs(center - v) <= radius) for v in observed])
    assert edges == actual['edges']
    near(expected, actual['expected_hz'])
    near(radii, actual['radius_hz'])
    for i, edge in enumerate(edges):
        indices = [j for j, yes in enumerate(edge) if yes]
        unique = len(indices) == 1 and sum(other[indices[0]] for other in edges) == 1
        assert actual['state'][i] == ('unique' if unique else 'ambiguous' if indices else 'absent')
        assert actual['chosen'][i] == (indices[0] if unique else None)
    r['graphs'] += 1

try:
    report = load(a.input / 'report.json')
    assert report['result'] == 'all48_native_low_inventories_and_resolution_observed'
    for name, h in report['sources'].items():
        assert sha(a.input / 'exact_sources' / name) == h == sha(repo / name)
    bands = report['plan']['bands_hz']
    known = load(a.input / 'controls.json')
    z = np.load(a.input / 'known.npz')
    hz, power = power_of(z['audio'])
    near(z['power'], power, 1e-12)
    # Exact-null tone bands contain FFT/window roundoff. Absolute power agrees,
    # but normalized descriptors there are ill-conditioned. Independently replay
    # their formulas from saved cells; retain the original failed direct check.
    verify_stats(hz, z['power'], known['known'], bands)
    near(z['inventory_cells'], power, 1e-12)
    verify_inventory(z['inventory_cells'], known['known_inventory'])
    _, gain_power = power_of(z['audio'] * 3)
    near(z['gain3_power'], gain_power, 1e-12)
    verify_stats(hz, z['gain3_power'], known['gain3'], bands)
    verify_stats(hz, np.zeros_like(power), known['silence'], bands)
    assert not known['original_separation_condition']
    graph([75], [86.25], 1.15, known['true_moving75'])
    graph([75], [86.25], 1., known['fixed_query'])
    parent = a.workspace / 'baselines/accel_ridges_v1'
    entries = {v['path']: v for v in load(parent / 'manifest.json')['files']}
    for name in report['plan']['segments']:
        original_json = parent / 'evidence/observe2' / (name + '.json')
        original_audio = parent / 'evidence/observe2' / (name + '.npz')
        for path in [original_json, original_audio]:
            assert sha(path) == entries[path.relative_to(parent).as_posix()]['sha256']
        old = load(original_json)
        audio = np.load(original_audio)['audio']
        data = load(a.input / name / 'observations.json')
        assert data['parent_json_sha256'] == sha(original_json) and data['parent_audio_sha256'] == sha(original_audio)
        refs = data['reference_hz']
        assert refs == data['rows'][0]['inventory']['hz'] and len(data['rows']) == len(old['guides'])
        for i, row in enumerate(data['rows']):
            z = np.load(a.input / name / f'tile_{i:02d}.npz')
            assert row['tile'] == i and row['guide'] == old['guides'][i]
            assert np.array_equal(z['audio'], audio[i * 12000:(i + 1) * 12000])
            hz, power = power_of(z['audio'])
            r['maximum_power_error'] = max(r['maximum_power_error'], near(power, z['cells'], 1e-12))
            verify_stats(hz, z['cells'], row, bands)
            near(z['inventory_cells'], power, 1e-12)
            verify_inventory(z['inventory_cells'], row['inventory'])
            ratio = row['guide']['ratio']
            union = row['inventory']['hz'] + old['inventories'][i]['hz']
            assert union == row['observed_union_hz']
            graph(refs, union, ratio, row['moving'])
            graph(refs, union, 1., row['fixed'])
            eligibility = [bool(i and row['guide']['supported'] and
                abs(f * (ratio - 1)) > 2 * max(4 * (1 + ratio) + f * ratio * (2 ** (.5 / 192) - 1),
                                             8 + f * (2 ** (.5 / 192) - 1))) for f in refs]
            assert eligibility == row['original_separation_eligible']
            r['windows'] += 1
        summary = next(v for v in report['observations'] if v['segment'] == name)
        powers = np.sum([v['band_power_LR'] for v in data['rows']], axis=0)
        total = np.sum([v['total_power_LR'] for v in data['rows']], axis=0)
        near(powers / total, summary['band_fraction_of_full_native_LR'])
        assert summary['total_low_peak_observations'] == sum(len(v['inventory']['hz']) for v in data['rows'])
        counts = [sum(v['original_separation_eligible'][k] for v in data['rows']) for k in range(len(refs))]
        assert summary['geometric_eligible_counts'] == counts
        r['summaries'].append(summary)
    invariant = a.workspace / 'baselines/idle_microtexture_c_v1/inputs'
    for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        table = load(invariant / filename)
        assert len(table) == count
        for name, h in table.items():
            assert sha(repo / name) == h
    r.update(result='all48_native_low_power_descriptors_scanned_peaks_and_graphs_verified',
        input_report_sha256=sha(a.input / 'report.json'), C_H_unchanged=612, old_voices_unchanged=67,
        physical_source_classification=False, new_audio_or_profile=False,
        descriptor_arithmetic_replayed_from_independently_power_verified_saved_cells=True,
        exact_null_band_normalized_descriptors_not_physically_precise=True,
        initial_direct_null_band_descriptor_failure_preserved=True,
        initial_direct_null_band_log_prominence_failure_preserved=True,
        crossing200_uses_original_frozen_upper_inventory=True,
        statistics_hanning_and_inventory_periodic_cos_cells_recorded_separately=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
print({key: r[key] for key in ['result', 'windows', 'peak_observations', 'graphs', 'maximum_power_error', 'maximum_descriptor_error', 'maximum_peak_error']})
