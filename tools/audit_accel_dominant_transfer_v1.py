"""Independent scalar dominant training, full graphs and all six predictions."""
import argparse
import itertools
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
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_audit.py')
r = dict(result='running', source_models=0, pairs=[], predicted_rows=0, outside_rows=0,
         maximum_model_error=0., maximum_prediction_error=0.)

def near(x, y):
    error = float(abs(np.asarray(x) - np.asarray(y)).max(initial=0))
    assert error <= 1e-10, error
    return error

def frozen_file(path, baseline):
    manifest = load(baseline / 'manifest.json')
    entry = next(v for v in manifest['files'] if v['path'] == path.relative_to(baseline).as_posix())
    assert sha(path) == entry['sha256'] and path.stat().st_size == entry['bytes']

def rows_for(rows, k):
    return [(row['tile'], row['ratio'], line) for row in rows if row['guide_supported']
            for line in row['lines'] if line['reference_index'] == k and line['eligible']]

def model_from(rows):
    if len(rows) < 3:
        return None
    x = [math.log(ratio) for _, ratio, _ in rows]
    if max(x) - min(x) < math.log(1.03):
        return None
    n = len(x)
    center = math.fsum(x) / n
    denominator = math.fsum((v - center) ** 2 for v in x)
    means, slopes, rms = [], [], []
    for c in range(2):
        values = [math.log(line['amplitude_LR'][c]) for _, _, line in rows]
        mean = math.fsum(values) / n
        means.append(mean)
        slopes.append(math.fsum((u - center) * (v - mean) for u, v in zip(x, values)) / denominator)
        rms.append(math.sqrt(math.fsum(line['amplitude_LR'][c] ** 2 for _, _, line in rows) / n))
    return dict(count=n, coordinate_mean=center, coordinate_min=min(x), coordinate_max=max(x),
        log_amplitude_mean_LR=means, slope_LR=slopes, RMS_amplitude_LR=rms,
        frequency_at_ratio1_hz=float(np.median([line['frequency_hz'] / ratio for _, ratio, line in rows])))

try:
    observed = load(a.input / 'report.json')
    assert observed['result'] == 'all6_corrected_dominant_transfers_complete'
    for name, h in observed['sources'].items():
        assert sha(a.input / 'exact_sources' / name) == h == sha(repo / name)
    for path, h in observed['input_hashes'].items():
        assert sha(path) == h
    baselines = a.workspace / 'baselines'
    fullbase = baselines / 'accel_reference_selection_v1'
    ridgebase = baselines / 'accel_ridges_v1'
    scalebase = baselines / 'accel_amplitude_v1'
    fits, refs, primaries, models = {}, {}, {}, {}
    for name in observed['plan']['segments']:
        fitfile = fullbase / 'evidence/accel_full_inventory_v1/observe1' / name / 'fits.json'
        ridgefile = ridgebase / 'evidence/observe2' / (name + '.json')
        frozen_file(fitfile, fullbase)
        frozen_file(ridgefile, ridgebase)
        fits[name] = load(fitfile)
        inv = load(ridgefile)['inventories'][0]
        refs[name] = inv['hz']
        k = max(range(len(refs[name])), key=lambda i: math.fsum(inv['power_LR'][i]))
        primaries[name] = k
        selected = rows_for(fits[name], k)
        models[name] = model_from(selected)
        item = observed['sources_data'][name]
        assert item['primary_reference'] == k and item['training_tiles'] == [i for i, _, _ in selected]
        near(item['initial_hz'], refs[name][k])
        near(item['native_peak_power_LR'], inv['power_LR'][k])
        near(item['reference_hz'], refs[name])
        assert (item['model'] is None) == (models[name] is None)
        if models[name] is not None:
            for key, value in models[name].items():
                r['maximum_model_error'] = max(r['maximum_model_error'], near(value, item['model'][key]))
            r['source_models'] += 1
    expected = list(itertools.permutations(observed['plan']['segments'], 2))
    assert len(observed['pairs']) == len(expected) == 6
    for item, (source, target) in zip(observed['pairs'], expected):
        assert (item['source'], item['target']) == (source, target)
        scale_file = scalebase / 'evidence/observe1' / (source + '_to_' + target + '.json')
        frozen_file(scale_file, scalebase)
        match = load(scale_file)['scale_match']
        assert item['original_scale_match'] == match
        ratio = match['ratio']
        graph = item['full_inventory_graph']
        edges = []
        for i, f in enumerate(refs[source]):
            center = f * ratio
            radius = 4 * (1 + ratio) + center * (2 ** (.5 / 192) - 1)
            near(center, graph['expected_hz'][i])
            near(radius, graph['radius_hz'][i])
            edges.append([int(abs(center - value) <= radius) for value in refs[target]])
        assert edges == graph['edges']
        states, chosen = [], []
        for edge in edges:
            indices = [i for i, yes in enumerate(edge) if yes]
            unique = len(indices) == 1 and sum(other[indices[0]] for other in edges) == 1
            states.append('unique' if unique else 'ambiguous' if indices else 'absent')
            chosen.append(indices[0] if unique else None)
        assert states == graph['state'] and chosen == graph['chosen']
        k = primaries[source]
        j = chosen[k]
        assert (item['source_reference'], item['target_reference'], item['target_primary_reference']) == (k, j, primaries[target])
        assert item['maps_to_target_primary'] == (j == primaries[target])
        model = models[source]
        status = 'scale_unsupported' if not match['supported'] else 'association_' + states[k] if states[k] != 'unique' else 'insufficient_training' if model is None else None
        inside = []
        if status is None:
            selected = rows_for(fits[target], j)
            assert len(selected) == len(item['rows'])
            for (tile, within_ratio, line), check in zip(selected, item['rows']):
                x = float(np.log(ratio * within_ratio))
                within = model['coordinate_min'] <= x <= model['coordinate_max']
                assert check['tile'] == tile and check['within_source_range'] == within
                near(x, check['coordinate'])
                near(line['frequency_hz'], check['observed_frequency_hz'])
                near(line['amplitude_LR'], check['observed_amplitude_LR'])
                if not within:
                    assert set(check) == {'tile', 'coordinate', 'within_source_range', 'observed_frequency_hz', 'observed_amplitude_LR'}
                    r['outside_rows'] += 1
                    continue
                # Use original independently checked coefficients to isolate prediction arithmetic.
                original = observed['sources_data'][source]['model']
                predictions = dict(RMS=original['RMS_amplitude_LR'],
                    geometric=[math.exp(v) for v in original['log_amplitude_mean_LR']],
                    log_linear=[math.exp(m + s * (x - original['coordinate_mean'])) for m, s in
                                zip(original['log_amplitude_mean_LR'], original['slope_LR'])])
                for key, prediction in predictions.items():
                    error = [20 / math.log(10) * (math.log(o) - math.log(v)) for o, v in zip(line['amplitude_LR'], prediction)]
                    r['maximum_prediction_error'] = max(r['maximum_prediction_error'],
                        near(prediction, check['predicted_amplitude_LR'][key]), near(error, check['error_db_LR'][key]))
                near(line['frequency_hz'] - original['frequency_at_ratio1_hz'] * math.exp(x), check['frequency_error_hz'])
                inside.append(check)
                r['predicted_rows'] += 1
            assert item['eligible_target_count'] == len(selected) and item['within_count'] == len(inside)
            status = 'compared' if len(inside) >= 3 and len(inside) >= .5 * len(selected) else 'insufficient_target_range'
            if status == 'compared':
                maximum = max(abs(check['frequency_error_hz']) for check in inside)
                near(maximum, item['maximum_frequency_error_hz'])
                for key in ['RMS', 'geometric', 'log_linear']:
                    error = float(np.median([abs(v) for check in inside for v in check['error_db_LR'][key]]))
                    near(error, item['median_absolute_error_db'][key])
                    assert item['both_diagnostics_pass'][key] == (error <= 3 and maximum <= 4)
        assert status == item['status']
        r['pairs'].append({key: item[key] for key in ['source', 'target', 'status', 'maps_to_target_primary',
                           'within_count', 'eligible_target_count', 'median_absolute_error_db',
                           'maximum_frequency_error_hz', 'both_diagnostics_pass'] if key in item})
    known = load(a.input / 'controls.json')
    assert known['full_inventory']['state'] == ['unique'] * 6
    assert known['missing']['state'][2] == 'absent' and known['adjacent']['state'][2] == 'ambiguous'
    assert known['original']['training_independent_of_target'] and known['original']['same_coordinate_does_not_determine_target_law']
    assert max(abs(v) for v in known['original']['changed_law_error_db_LR']) > 3
    invariant = baselines / 'idle_microtexture_c_v1/inputs'
    for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(invariant / filename)
        assert len(values) == count
        for name, h in values.items():
            assert sha(repo / name) == h
    r.update(result='all3_source_models_full_graphs_and6_dominant_transfers_verified',
        input_report_sha256=sha(a.input / 'report.json'), frozen_parent_files_verified=True,
        scale_matches_reused_without_new_search=True, C_H_unchanged=612, old_voices_unchanged=67,
        common_phase_RPM_load_or_source_identity=False, new_audio_or_profile=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
print({key: r[key] for key in ['result', 'source_models', 'predicted_rows', 'outside_rows', 'maximum_model_error', 'maximum_prediction_error']})
