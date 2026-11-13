"""Source-only transfer of the three previously omitted dominant references."""
import argparse
import itertools
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from accel_amplitude_v1.model import compile_model, predict, train_rows
from accel_amplitude_v1.checks import controls
from accel_ridges_v1.observe import associate

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, input_hashes={}, sources_data={}, pairs=[])
try:
    plan = load(repo / 'research/accel_dominant_transfer_v1_plan.json')
    scale_plan = load(repo / 'research/accel_material_v1_plan.json')
    ridge_plan = load(repo / 'research/accel_ridges_v1_plan.json')
    paths = [Path(__file__), repo / 'research/accel_dominant_transfer_v1_plan.json',
             repo / 'research/accel_material_v1_plan.json', repo / 'research/accel_ridges_v1_plan.json',
             repo / 'tools/research_archive_v1.py', repo / 'tools/accel_ridges_v1/observe.py',
             repo / 'tools/accel_material_v1/features.py', repo / 'tools/accel_material_v1/checks.py',
             repo / 'tools/idle_material_v1/features.py',
             *sorted((repo / 'tools/accel_amplitude_v1').glob('*.py'))]
    for path in paths:
        name = path.relative_to(repo).as_posix()
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['sources'][name] = sha(path)
    known = controls(scale_plan, ridge_plan)
    frequencies = np.array([217.3, 245.1, 299.8, 419.7, 899.1, 1499.])
    shifted = frequencies * 1.01
    base = associate(frequencies, shifted, 1.01, 4., ridge_plan)
    absent = associate(frequencies, np.delete(shifted, 2), 1.01, 4., ridge_plan)
    ambiguous = associate(frequencies, np.sort(np.r_[shifted, shifted[2] + 3]), 1.01, 4., ridge_plan)
    assert base['state'] == ['unique'] * 6
    assert absent['state'][2] == 'absent' and ambiguous['state'][2] == 'ambiguous'
    save(a.out / 'controls.json', dict(original=known, full_inventory=base, missing=absent, adjacent=ambiguous))

    def read_input(path):
        r['input_hashes'][str(path)] = sha(path)
        return load(path)

    fits_root = a.workspace / 'baselines/accel_reference_selection_v1/evidence/accel_full_inventory_v1/observe1'
    ridge_root = a.workspace / 'baselines/accel_ridges_v1/evidence/observe2'
    scale_root = a.workspace / 'baselines/accel_amplitude_v1/evidence/observe1'
    fitted, refs, primary, models = {}, {}, {}, {}
    for name in plan['segments']:
        fitted[name] = read_input(fits_root / name / 'fits.json')
        source = read_input(ridge_root / (name + '.json'))
        inv = source['inventories'][0]
        refs[name] = inv['hz']
        primary[name] = int(np.argmax(np.sum(inv['power_LR'], axis=1)))
        selected = train_rows(fitted[name], primary[name])
        model = compile_model([np.log(ratio) for _, ratio, _ in selected],
                              [line['amplitude_LR'] for _, _, line in selected],
                              [line['frequency_hz'] for _, _, line in selected],
                              [ratio for _, ratio, _ in selected], np.log(1.03)) if selected else None
        models[name] = model
        r['sources_data'][name] = dict(primary_reference=primary[name], initial_hz=refs[name][primary[name]],
            native_peak_power_LR=inv['power_LR'][primary[name]], reference_hz=refs[name],
            training_tiles=[i for i, _, _ in selected], model=model)
    for source, target in itertools.permutations(plan['segments'], 2):
        original = read_input(scale_root / (source + '_to_' + target + '.json'))
        match = original['scale_match']
        graph = associate(refs[source], refs[target], match['ratio'], 4., ridge_plan)
        k = primary[source]
        j = graph['chosen'][k]
        model = models[source]
        row = dict(source=source, target=target, source_reference=k, target_reference=j,
                   target_primary_reference=primary[target], maps_to_target_primary=j == primary[target],
                   original_scale_match=match, full_inventory_graph=graph, rows=[])
        if not match['supported']:
            row['status'] = 'scale_unsupported'
        elif graph['state'][k] != 'unique':
            row['status'] = 'association_' + graph['state'][k]
        elif model is None:
            row['status'] = 'insufficient_training'
        else:
            selected = train_rows(fitted[target], j)
            inside = []
            for tile, ratio, line in selected:
                x = float(np.log(match['ratio'] * ratio))
                within = model['coordinate_min'] <= x <= model['coordinate_max']
                check = dict(tile=tile, coordinate=x, within_source_range=within,
                    observed_frequency_hz=line['frequency_hz'], observed_amplitude_LR=line['amplitude_LR'])
                if within:
                    pred = predict(model, x)
                    check.update(predicted_amplitude_LR={key: value.tolist() for key, value in pred.items()},
                        error_db_LR={key: (20 * np.log10(np.asarray(line['amplitude_LR']) / value)).tolist()
                                     for key, value in pred.items()},
                        frequency_error_hz=float(line['frequency_hz'] - model['frequency_at_ratio1_hz'] * np.exp(x)))
                    inside.append(check)
                row['rows'].append(check)
            row.update(eligible_target_count=len(selected), within_count=len(inside))
            row['status'] = 'compared' if len(inside) >= 3 and len(inside) >= .5 * len(selected) else 'insufficient_target_range'
            if row['status'] == 'compared':
                row['median_absolute_error_db'] = {key: float(np.median(abs(np.array([v['error_db_LR'][key] for v in inside]))))
                                                  for key in ['RMS', 'geometric', 'log_linear']}
                row['maximum_frequency_error_hz'] = max(abs(v['frequency_error_hz']) for v in inside)
                row['both_diagnostics_pass'] = {key: value <= 3 and row['maximum_frequency_error_hz'] <= 4
                                               for key, value in row['median_absolute_error_db'].items()}
        r['pairs'].append(row)
        print({key: row[key] for key in ['source', 'target', 'status', 'maps_to_target_primary']}, flush=True)
    r.update(result='all6_corrected_dominant_transfers_complete', plan=plan,
             no_audio_or_profile=True, runtime_changed=False, measured_RPM_load_or_common_phase=False,
             pristine_holdout=False, target_amplitude_used_for_training=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
