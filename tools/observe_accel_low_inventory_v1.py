"""Every native low-band observation; no source fitting or rumble classification."""
import argparse
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
from accel_ridges_v1.observe import inventory, associate

def inventory_cells(audio):
    """Record exact original inventory arithmetic, separate from np.hanning stats."""
    n = len(audio)
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(n) / n)
    power = abs(np.fft.rfft(audio * window[:, None], axis=0)) ** 2 * 2 / (n * np.sum(window * window))
    power[[0, -1]] *= .5
    return power

def observe(audio, bands):
    n = len(audio)
    window = np.hanning(n + 1)[:-1]
    hz = np.fft.rfftfreq(n, 1 / 48000)
    power = abs(np.fft.rfft(audio * window[:, None], axis=0)) ** 2 * 2 / (n * np.sum(window * window))
    power[[0, -1]] *= .5
    total = power.sum(axis=0)
    band_power, descriptors = [], []
    for lo, hi in bands:
        indices = np.flatnonzero((hz >= lo) & (hz < hi))
        z = power[indices]
        band_power.append(z.sum(axis=0))
        row = []
        for c in range(2):
            values = z[:, c]
            if not len(values) or values.sum() == 0:
                row.append(None)
                continue
            concentration = max(float(values[max(0, i - 1):min(len(values), i + 2)].sum())
                                for i in range(len(values))) / float(values.sum())
            flatness = float(np.exp(np.log(np.maximum(values, np.finfo(float).tiny)).mean()) / values.mean())
            row.append(dict(flatness=flatness, maximum_cell_hz=float(hz[indices[np.argmax(values)]]),
                            maximum_three_cell_fraction=concentration))
        descriptors.append(row)
    band_power = np.asarray(band_power)
    fractions = np.divide(band_power, total, out=np.zeros_like(band_power), where=total > 0)
    return dict(total_power_LR=total.tolist(), band_power_LR=band_power.tolist(),
                band_fraction_of_full_native_LR=fractions.tolist(), descriptors=descriptors), power

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, observations=[])
try:
    plan = load(repo / 'research/accel_low_inventory_v1_plan.json')
    ridge = load(repo / 'research/accel_ridges_v1_plan.json')
    ridge['inventory_hz'] = [30, 200]
    for path in [Path(__file__), repo / 'research/accel_low_inventory_v1_plan.json',
                 repo / 'research/accel_ridges_v1_plan.json', repo / 'tools/accel_ridges_v1/observe.py',
                 repo / 'tools/research_archive_v1.py']:
        name = path.relative_to(repo).as_posix()
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['sources'][name] = sha(path)
    n = 12000
    t = np.arange(n) / 48000
    tone = .2 * np.cos(2 * np.pi * 76 * t + .3) + .07 * np.cos(2 * np.pi * 148 * t - .4)
    known = np.column_stack((tone, .7 * tone))
    values, power = observe(known, plan['bands_hz'])
    inv = inventory(known, ridge)
    assert len(inv['hz']) == 2 and max(abs(np.asarray(inv['hz']) - [76, 148])) < .01
    truth = np.array([1., .49]) * (.2 ** 2 + .07 ** 2) / 2
    assert abs(np.asarray(values['total_power_LR']) - truth).max() < 1e-14
    scaled, scaled_power = observe(known * 3, plan['bands_hz'])
    assert abs(np.asarray(scaled['band_power_LR']) - 9 * np.asarray(values['band_power_LR'])).max() < 1e-14
    # Band descriptors with only numerical leakage are not invariant; test actual tone band only.
    for c in range(2):
        for key in ['flatness', 'maximum_three_cell_fraction']:
            assert abs(scaled['descriptors'][3][c][key] - values['descriptors'][3][c][key]) < 1e-12
    silent, silent_power = observe(np.zeros((n, 2)), plan['bands_hz'])
    assert not silent_power.any() and all(v == [None, None] for v in silent['descriptors'])
    moving = associate([75.], [75 * 1.15], 1.15, 4., ridge)
    fixed = associate([75.], [75 * 1.15], 1., 4., ridge)
    # Their uncertainty regions overlap, even though center query to moving observation may be absent at fixed center.
    separation = abs(moving['expected_hz'][0] - fixed['expected_hz'][0]) > 2 * max(moving['radius_hz'][0], fixed['radius_hz'][0])
    assert not separation
    save(a.out / 'controls.json', dict(known=values, known_inventory=inv, gain3=scaled, silence=silent,
        true_moving75=moving, fixed_query=fixed, original_separation_condition=False,
        warning='This genuine moving low line does not satisfy original geometric resolvability; absence of classification is not absence of engine movement.'))
    np.savez_compressed(a.out / 'known.npz', audio=known, power=power, gain3_power=scaled_power,
                        inventory_cells=inventory_cells(known))
    parent = a.workspace / 'baselines/accel_ridges_v1/evidence/observe2'
    for name in plan['segments']:
        input_json, input_audio = parent / (name + '.json'), parent / (name + '.npz')
        old = load(input_json)
        audio = np.load(input_audio)['audio']
        folder = a.out / name
        folder.mkdir()
        observations, inventories = [], []
        for i, guide in enumerate(old['guides']):
            tile = audio[i * n:(i + 1) * n]
            stats, cells = observe(tile, plan['bands_hz'])
            inv = inventory(tile, ridge)
            observations.append(dict(tile=i, guide=guide, **stats, inventory=inv))
            inventories.append(inv)
            np.savez_compressed(folder / f'tile_{i:02d}.npz', audio=tile, cells=cells,
                                inventory_cells=inventory_cells(tile))
        refs = inventories[0]['hz']
        for row in observations:
            ratio = row['guide']['ratio']
            upper = old['inventories'][row['tile']]
            union = row['inventory']['hz'] + upper['hz']
            assert not row['inventory']['bin'] or not upper['bin'] or row['inventory']['bin'][-1] < upper['bin'][0]
            moving = associate(refs, union, ratio, 4., ridge)
            fixed = associate(refs, union, 1., 4., ridge)
            row.update(moving=moving, fixed=fixed, observed_union_hz=union,
                original_separation_eligible=[bool(row['tile'] and row['guide']['supported'] and
                    abs(x - y) > 2 * max(rx, ry)) for x, y, rx, ry in zip(
                    moving['expected_hz'], fixed['expected_hz'], moving['radius_hz'], fixed['radius_hz'])])
        save(folder / 'observations.json', dict(parent_json_sha256=sha(input_json), parent_audio_sha256=sha(input_audio),
            reference_hz=refs, rows=observations))
        powers = np.sum([v['band_power_LR'] for v in observations], axis=0)
        total = np.sum([v['total_power_LR'] for v in observations], axis=0)
        summary = dict(segment=name, tiles=len(observations), first_reference_hz=refs,
            band_fraction_of_full_native_LR=(powers / total).tolist(),
            total_low_peak_observations=sum(len(v['inventory']['hz']) for v in observations),
            geometric_eligible_counts=[sum(v['original_separation_eligible'][k] for v in observations) for k in range(len(refs))],
            graph_observed_nodes='low original30..200 inventory UNION unchanged frozen200..7000 inventory; separate original floors',
            warning='Descriptive native inventory; no moving/fixed/engine/wind source labels or continuous source inferred.')
        r['observations'].append(summary)
        print(summary, flush=True)
    r.update(result='all48_native_low_inventories_and_resolution_observed', plan=plan,
        source_classification=False, new_audio_or_profile=False, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
