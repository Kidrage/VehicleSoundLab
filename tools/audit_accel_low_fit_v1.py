"""Independent native waves, observed initialization, tracks and held-window checks."""
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
from research_archive_v1 import load, save, sha
from native_chirp_audit_v1.wave import near, audit_wave
from native_chirp_audit_v1.temporal import audit_temporal, audit_predictions

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_audit.py')
r = dict(result='running', waveforms=0, lines=0, maximum_waveform_error=0., maximum_support_error=0.,
         maximum_phase_arithmetic_error=0., maximum_known_signal_error=0., summaries=[])

def initialization(inventories, ratios, actual):
    assert len(inventories) == len(actual)
    for i, inv in enumerate(inventories):
        near(np.array(inv['bin']) * 4, [round(v / 4) * 4 for v in inv['hz']])
        neighbors = [j for j in [i - 1, i + 1] if 0 <= j < len(inventories)]
        assert sorted(map(int, actual[i]['neighbor_graphs'])) == neighbors
        graphs = {}
        for j in neighbors:
            ratio = ratios[j] / ratios[i]
            edges, expected, radii = [], [], []
            for f in inv['hz']:
                center = f * ratio
                radius = 4 * (1 + ratio) + center * (2 ** (.5 / 192) - 1)
                expected.append(center)
                radii.append(radius)
                edges.append([int(abs(center - g) <= radius) for g in inventories[j]['hz']])
            graph = actual[i]['neighbor_graphs'][str(j)]
            assert graph['edges'] == edges
            near(expected, graph['expected_hz'])
            near(radii, graph['radius_hz'])
            for k, edge in enumerate(edges):
                choices = [v for v, yes in enumerate(edge) if yes]
                unique = len(choices) == 1 and sum(other[choices[0]] for other in edges) == 1
                state = 'unique' if unique else 'ambiguous' if choices else 'absent'
                assert state == graph['state'][k] and graph['chosen'][k] == (choices[0] if unique else None)
            graphs[j] = graph
        for k in range(len(inv['hz'])):
            available = [j for j in neighbors if graphs[j]['state'][k] == 'unique']
            def f(j):
                return inventories[j]['hz'][graphs[j]['chosen'][k]]
            q = (f(i + 1) - f(i - 1)) / .5 if len(available) == 2 else (f(available[0]) - inv['hz'][k]) / ((available[0] - i) * .25) if available else 0
            near(q, actual[i]['initial_chirp'][k])

def wave(z, row, inv, init, fit_plan):
    out = audit_wave(z, row, fit_plan)
    if row['lines']:
        assert len(row['lines']) == len(inv['bin'])
        near(z['nominal'], np.array(inv['bin']) * 4)
        near(z['initial'][len(inv['bin']):2 * len(inv['bin'])], np.clip(init['initial_chirp'], -500 + 1e-6, 500 - 1e-6))
        for k, line in enumerate(row['lines']):
            assert (line['native_inventory_index'], line['native_bin'], line['native_peak_hz']) == (k, inv['bin'][k], inv['hz'][k])
    else:
        assert len(inv['bin']) == 0 or len(inv['bin']) > 64
    r['waveforms'] += 1
    r['lines'] += out['lines']
    r['maximum_waveform_error'] = max(r['maximum_waveform_error'], out['waveform_error'])
    r['maximum_support_error'] = max(r['maximum_support_error'], out['support_error'])

def parent_file(path, baseline):
    record = next(v for v in load(baseline / 'manifest.json')['files'] if v['path'] == path.relative_to(baseline).as_posix())
    assert sha(path) == record['sha256']

try:
    report = load(a.input / 'report.json')
    assert report['result'] == 'all48_native_low_upper_joint_fits_and_temporal_checks_complete'
    for name, h in report['sources'].items():
        assert sha(a.input / 'exact_sources' / name) == h == sha(repo / name)
    fit_plan = load(repo / 'research/accel_chirp_v1_plan.json')
    link_plan = load(repo / 'research/low_chirp_v1_plan.json')
    known = load(a.input / 'controls.json')
    signal = known['signal_parameters']
    base, q, amp, phase = [np.asarray(signal[key]) for key in ['base_hz', 'q_hzs', 'amplitude_L', 'phase_radians']]
    centers = signal['centers_seconds']
    ratios = [1 + .05 * v for v in centers]
    initialization(known['inventories'], ratios, known['initialization'])
    for i, row in enumerate(known['rows']):
        z = np.load(a.input / 'known' / ('tile_' + str(i) + '.npz'))
        t = np.array([centers[i] + (j - 6000) / 48000 for j in range(12000)])
        angle = 2 * np.pi * (t[:, None] * base + .5 * t[:, None] ** 2 * q) + phase
        expected = np.column_stack(((np.exp(1j * angle) @ amp).real,
            (np.exp(1j * (angle + signal['right_phase_radians'])) @ (amp * signal['right_gain'])).real))
        r['maximum_known_signal_error'] = max(r['maximum_known_signal_error'], near(expected, z['audio'], 2e-12))
        wave(z, row, known['inventories'][i], known['initialization'][i], fit_plan)
        assert row['success'] and len(row['lines']) == 10 and all(v['eligible'] for v in row['lines'])
        near(base + q * centers[i], known['truth'][i]['frequency_hz'])
        assert max(abs(v['frequency_hz'] - f) for v, f in zip(row['lines'], base + q * centers[i])) < .06
        assert max(abs(v['chirp_hz_per_second'] - f) for v, f in zip(row['lines'], q)) < .15
        assert np.linalg.norm(z['residual']) / np.linalg.norm(z['audio']) < 1e-5
    value = audit_temporal(known['rows'], known['temporal'], link_plan)
    assert value['tracks'] == 10 and all(len(v['windows']) == 12 for v in known['temporal']['tracks'])
    r['maximum_phase_arithmetic_error'] = max(r['maximum_phase_arithmetic_error'], value['maximum_phase_arithmetic_error'])
    for name, case in known['counterexamples'].items():
        z = np.load(a.input / 'known' / (name + '.npz'))
        initialization([case['inventory']], [1.], [case['initialization']])
        wave(z, case['fit'], case['inventory'], case['initialization'], fit_plan)
        if name == 'same_mono_noise':
            near(z['audio'][:, 1], .67 * z['audio'][:, 0], 0)
        if name == 'silence':
            assert not z['audio'].any()
        if name == 'missing_low_with_neighbor':
            assert case['forced_absent_native_bin'] == 45 and case['forced_absent_frequency_hz'] == 180
            assert not next(v for v in case['fit']['lines'] if v['nominal_hz'] == 180)['eligible']
    baselines = a.workspace / 'baselines'
    low_root = baselines / 'accel_low_inventory_v1'
    ridge_root = baselines / 'accel_ridges_v1'
    for name in report['plan']['segments']:
        low_file = low_root / 'evidence/observe4' / name / 'observations.json'
        upper_file = ridge_root / 'evidence/observe2' / (name + '.json')
        for path, parent in [(low_file, low_root), (upper_file, ridge_root)]:
            parent_file(path, parent)
            assert report['parent_hashes'][str(path)] == sha(path)
        low, upper = load(low_file), load(upper_file)
        saved = load(a.input / name / 'initialization.json')
        invs = saved['inventories']
        for i, inv in enumerate(invs):
            assert inv == dict(bin=low['rows'][i]['inventory']['bin'] + upper['inventories'][i]['bin'], hz=low['rows'][i]['observed_union_hz'])
        initialization(invs, [v['guide']['ratio'] for v in low['rows']], saved['initial'])
        rows = load(a.input / name / 'fits.json')
        assert len(rows) == len(low['rows'])
        for i, row in enumerate(rows):
            source = low_root / 'evidence/observe4' / name / f'tile_{i:02d}.npz'
            parent_file(source, low_root)
            z = np.load(a.input / name / f'tile_{i:02d}.npz')
            assert np.array_equal(z['audio'], np.load(source)['audio']) and row['input_sha256'] == sha(source)
            assert row['tile'] == i and row['ratio'] == low['rows'][i]['guide']['ratio'] and row['guide_supported'] == low['rows'][i]['guide']['supported']
            wave(z, row, invs[i], saved['initial'][i], fit_plan)
        linked = load(a.input / name / 'temporal.json')
        predicted = load(a.input / name / 'predictions.json')
        value = audit_temporal(rows, linked, link_plan)
        prediction = audit_predictions(rows, linked, predicted)
        r['maximum_phase_arithmetic_error'] = max(r['maximum_phase_arithmetic_error'], value['maximum_phase_arithmetic_error'])
        summary = dict(segment=name, windows=len(rows), successful=sum(v['success'] for v in rows),
            local_lines=sum(len(v['lines']) for v in rows), eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            low_start_tracks=prediction['low_start_tracks'], low_tracks_atleast5=sum(v['frequencies_hz'][0] < 200 and len(v['windows']) >= 5 for v in linked['tracks']),
            compared_low_tracks=prediction['compared_low_tracks'])
        assert summary == next(v for v in report['observations'] if v['segment'] == name)
        r['summaries'].append(dict(**summary, failed_windows=[v['tile'] for v in rows if not v['success']],
            longest_low_track=max((len(v['windows']) for v in linked['tracks'] if v['frequencies_hz'][0] < 200), default=0)))
    for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        table = load(baselines / 'idle_microtexture_c_v1/inputs' / filename)
        assert len(table) == count
        for name, h in table.items():
            assert sha(repo / name) == h
    r.update(result='all_known_and48_native_waves_initials_tracks_phase_reports_predictions_verified',
        input_report_sha256=sha(a.input / 'report.json'), C_H_unchanged=612, old_voices_unchanged=67,
        original_grouping_replayed_after_independent_complex_wave_check=True,
        engine_common_phase_RPM_load_or_source_identity=False, new_audio_or_profile=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
print({key: r[key] for key in ['result', 'waveforms', 'lines', 'maximum_waveform_error', 'maximum_support_error', 'maximum_phase_arithmetic_error']})
