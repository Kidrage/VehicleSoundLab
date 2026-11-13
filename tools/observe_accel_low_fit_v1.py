"""Known full-path controls then native joint fits of every low+upper F3 candidate."""
import argparse
import shutil
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
p.add_argument('--controls-only', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from accel_low_fit_v1.observe import initial_graphs, fit_tile, temporal, predictions
from accel_low_fit_v1.checks import controls

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, observations=[])
try:
    plan = load(repo / 'research/accel_low_fit_v1_plan.json')
    fit_plan = load(repo / 'research/accel_chirp_v1_plan.json')
    ridge_plan = load(repo / 'research/accel_ridges_v1_plan.json')
    link_plan = load(repo / 'research/low_chirp_v1_plan.json')
    paths = [Path(__file__), repo / 'research/accel_low_fit_v1_plan.json',
        repo / 'research/accel_chirp_v1_plan.json', repo / 'research/accel_ridges_v1_plan.json',
        repo / 'research/low_chirp_v1_plan.json', repo / 'tools/research_archive_v1.py',
        repo / 'tools/accel_chirp_v1/fit.py', repo / 'tools/line_motion_v1/local_chirps.py',
        repo / 'tools/accel_ridges_v1/observe.py', repo / 'tools/low_chirp_v1/link.py',
        *sorted((repo / 'tools/accel_low_fit_v1').glob('*.py'))]
    for path in paths:
        name = path.relative_to(repo).as_posix()
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['sources'][name] = sha(path)
    progress = a.out / 'known_progress'
    progress.mkdir()
    def checkpoint(name, metadata, arrays):
        save(progress / (name + '.json'), metadata)
        np.savez_compressed(progress / (name + '.npz'), **arrays)
    known, fixtures = controls(fit_plan, ridge_plan, link_plan, checkpoint)
    save(a.out / 'controls.json', known)
    folder = a.out / 'known'
    folder.mkdir()
    for i, arrays in enumerate(fixtures):
        name = arrays.get('name', 'tile_' + str(i))
        np.savez_compressed(folder / (name + '.npz'), **{k: v for k, v in arrays.items() if k != 'name'})
    print(dict(stage='known_controls_complete', tracks=len(known['temporal']['tracks'])), flush=True)
    r['controls_complete'] = True
    save(a.out / 'report.json', r)
    if a.controls_only:
        r['result'] = 'known_controls_only'
        raise SystemExit
    low_root = a.workspace / 'baselines/accel_low_inventory_v1/evidence/observe4'
    upper_root = a.workspace / 'baselines/accel_ridges_v1/evidence/observe2'
    r['parent_hashes'] = {}
    for name in plan['segments']:
        low_file = low_root / name / 'observations.json'
        upper_file = upper_root / (name + '.json')
        low, upper = load(low_file), load(upper_file)
        r['parent_hashes'][str(low_file)] = sha(low_file)
        r['parent_hashes'][str(upper_file)] = sha(upper_file)
        inventories = [dict(bin=v['inventory']['bin'] + upper['inventories'][i]['bin'], hz=v['observed_union_hz'])
                       for i, v in enumerate(low['rows'])]
        ratios = [v['guide']['ratio'] for v in low['rows']]
        initial = initial_graphs(inventories, ratios, ridge_plan)
        folder = a.out / name
        folder.mkdir()
        save(folder / 'initialization.json', dict(inventories=inventories, initial=initial))
        rows = []
        for i, inv in enumerate(inventories):
            source = low_root / name / f'tile_{i:02d}.npz'
            audio = np.load(source)['audio']
            begin = time.perf_counter()
            result, arrays = fit_tile(audio, inv, initial[i], fit_plan)
            result.update(tile=i, ratio=ratios[i], guide_supported=low['rows'][i]['guide']['supported'],
                          input_sha256=sha(source), seconds=time.perf_counter() - begin)
            rows.append(result)
            save(folder / 'fits.json', rows)
            np.savez_compressed(folder / f'tile_{i:02d}.npz', audio=audio, **arrays)
            print(dict(segment=name, tile=i, lines=len(inv['bin']), success=result['success'],
                eligible=sum(v['eligible'] for v in result['lines']), seconds=result['seconds']), flush=True)
        linked = temporal(rows, link_plan)
        predicted = predictions(rows, linked)
        save(folder / 'temporal.json', linked)
        save(folder / 'predictions.json', predicted)
        summary = dict(segment=name, windows=len(rows), successful=sum(v['success'] for v in rows),
            local_lines=sum(len(v['lines']) for v in rows), eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            low_start_tracks=sum(v['frequencies_hz'][0] < 200 for v in linked['tracks']),
            low_tracks_atleast5=sum(v['frequencies_hz'][0] < 200 and len(v['windows']) >= 5 for v in linked['tracks']),
            compared_low_tracks=sum(v['status'] == 'compared' for v in predicted))
        r['observations'].append(summary)
        save(a.out / 'report.json', r)
        print(summary, flush=True)
    r.update(result='all48_native_low_upper_joint_fits_and_temporal_checks_complete', plan=plan,
             audio_or_profile_exported=False, runtime_changed=False, common_phase_RPM_load_or_source_identity=False)
except SystemExit:
    raise
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
