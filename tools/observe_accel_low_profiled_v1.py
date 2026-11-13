"""Exact reduced-objective controls then all unchanged native source candidates."""
import argparse
import shutil
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
from scipy.linalg import lstsq
from research_archive_v1 import load, save, sha
from native_profiled_chirp_v1.fit import projection, fit
from accel_low_fit_v1.observe import temporal, predictions

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, observations=[])
try:
    plan = load(repo / 'research/accel_low_profiled_v1_plan.json')
    fit_plan = load(repo / 'research/accel_chirp_v1_plan.json')
    link_plan = load(repo / 'research/low_chirp_v1_plan.json')
    parent = a.workspace / 'references/analysis/accel_low_fit_v1/observe2'
    previous = load(parent / 'report.json')
    assert previous['result'] == 'all48_native_low_upper_joint_fits_and_temporal_checks_complete'
    for path in [Path(__file__), repo / 'research/accel_low_profiled_v1_plan.json', repo / 'research/accel_chirp_v1_plan.json',
        repo / 'research/low_chirp_v1_plan.json', repo / 'tools/research_archive_v1.py',
        repo / 'tools/native_profiled_chirp_v1/fit.py', repo / 'tools/accel_low_fit_v1/observe.py', repo / 'tools/low_chirp_v1/link.py']:
        name = path.relative_to(repo).as_posix()
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['sources'][name] = sha(path)
    r['parent_report_sha256'] = sha(parent / 'report.json')
    r['input_hashes'] = {}
    n = 12000
    t = (np.arange(n) - n / 2) / 48000
    w = np.sqrt((.5 - .5 * np.cos(2 * np.pi * np.arange(n) / n)) / n)
    nominal = np.array([76., 148., 300.])
    rng = np.random.default_rng(349117)
    x = np.cos(2 * np.pi * (t[:, None] * [76.3, 147.7, 300.2] + .5 * t[:, None] ** 2 * [13., -5., 11.]) + [.2, .4, -.8]) @ [.2, .07, .1] + .007 * rng.normal(size=n)
    p0 = np.array([.31, -.43, .27, 11., -7., 15.])
    fun, jac, state = projection(x, nominal, w, t)
    analytic = jac(p0)
    numeric = []
    for k in range(6):
        step = np.zeros(6)
        step[k] = 1e-5
        numeric.append((fun(p0 + step) - fun(p0 - step)) / 2e-5)
    numeric = np.column_stack(numeric)
    s = state(p0)
    oracle = lstsq(s['weighted'], w * x, lapack_driver='gelsd')[0]
    residual = s['weighted'] @ oracle - w * x
    probe = dict(maximum_Jacobian_error=float(abs(analytic - numeric).max()),
        maximum_SVD_residual_error=float(abs(residual - fun(p0)).max()),
        nonzero_residual_norm=float(np.linalg.norm(residual)), original_finite_difference_gate=1e-8)
    save(a.out / 'projection_control.json', probe)
    np.savez_compressed(a.out / 'projection_control.npz', audio=x, parameters=p0, nominal=nominal,
                        weight=w, time=t, analytic=analytic, numeric=numeric, QR_residual=fun(p0), SVD_residual=residual)
    assert probe['maximum_Jacobian_error'] < 1e-8 and probe['maximum_SVD_residual_error'] < 1e-12
    known = load(parent / 'controls.json')
    r['input_hashes'][str(parent / 'controls.json')] = sha(parent / 'controls.json')
    folder = a.out / 'known'
    folder.mkdir()
    rows = []
    def run(audio, inv, init):
        result, saved = fit(audio, np.array(inv['bin']) * 4., init['initial_chirp'], fit_plan)
        for k, line in enumerate(result['lines']):
            line.update(native_inventory_index=k, native_bin=inv['bin'][k], native_peak_hz=inv['hz'][k])
        return result, saved
    for i, original in enumerate(known['rows']):
        source = parent / 'known' / ('tile_' + str(i) + '.npz')
        r['input_hashes'][str(source)] = sha(source)
        audio = np.load(source)['audio']
        result, saved = run(audio, known['inventories'][i], known['initialization'][i])
        rows.append(result)
        save(folder / 'rows.json', rows)
        np.savez_compressed(folder / ('tile_' + str(i) + '.npz'), audio=audio, **saved)
        assert result['success'] and len(result['lines']) == 10 and all(v['eligible'] for v in result['lines'])
        assert max(abs(v['frequency_hz'] - f) for v, f in zip(result['lines'], known['truth'][i]['frequency_hz'])) < .06
        assert max(abs(v['chirp_hz_per_second'] - f) for v, f in zip(result['lines'], known['truth'][i]['q_hzs'])) < .15
        assert np.linalg.norm(saved['residual']) / np.linalg.norm(audio) < 1e-5
    linked = temporal(rows, link_plan)
    save(folder / 'temporal.json', linked)
    assert len(linked['tracks']) == 10 and all(len(v['windows']) == 12 for v in linked['tracks'])
    counters = {}
    for name, case in known['counterexamples'].items():
        source = parent / 'known' / (name + '.npz')
        r['input_hashes'][str(source)] = sha(source)
        audio = np.load(source)['audio']
        result, saved = run(audio, case['inventory'], case['initialization'])
        counters[name] = result
        save(folder / 'counterexamples.json', counters)
        np.savez_compressed(folder / (name + '.npz'), audio=audio, **saved)
        if name == 'missing_low_with_neighbor':
            assert not next(v for v in result['lines'] if v['nominal_hz'] == 180)['eligible']
    r['controls_complete'] = True
    save(a.out / 'report.json', r)
    print(dict(stage='profiled_controls_pass', **probe), flush=True)
    for name in previous['plan']['segments']:
        inputs = parent / name / 'initialization.json'
        r['input_hashes'][str(inputs)] = sha(inputs)
        initial = load(inputs)
        originals = load(parent / name / 'fits.json')
        r['input_hashes'][str(parent / name / 'fits.json')] = sha(parent / name / 'fits.json')
        folder = a.out / name
        folder.mkdir()
        rows = []
        for i, inv in enumerate(initial['inventories']):
            source = parent / name / f'tile_{i:02d}.npz'
            r['input_hashes'][str(source)] = sha(source)
            audio = np.load(source)['audio']
            begin = time.perf_counter()
            result, saved = run(audio, inv, initial['initial'][i])
            result.update(tile=i, ratio=originals[i]['ratio'], guide_supported=originals[i]['guide_supported'],
                          seconds=time.perf_counter() - begin, original_success=originals[i]['success'], original_cost=originals[i]['cost'])
            rows.append(result)
            save(folder / 'fits.json', rows)
            np.savez_compressed(folder / f'tile_{i:02d}.npz', audio=audio, **saved)
            print(dict(segment=name, tile=i, success=result['success'], original=originals[i]['success'],
                evaluations=result['evaluations'], seconds=result['seconds']), flush=True)
        linked = temporal(rows, link_plan)
        predicted = predictions(rows, linked)
        save(folder / 'temporal.json', linked)
        save(folder / 'predictions.json', predicted)
        summary = dict(segment=name, windows=len(rows), successful=sum(v['success'] for v in rows),
            local_lines=sum(len(v['lines']) for v in rows), eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            low_tracks_atleast5=sum(v['frequencies_hz'][0] < 200 and len(v['windows']) >= 5 for v in linked['tracks']),
            compared_low_tracks=sum(v['status'] == 'compared' for v in predicted))
        r['observations'].append(summary)
        save(a.out / 'report.json', r)
        print(summary, flush=True)
    r.update(result='all48_exact_profiled_native_fits_and_temporal_checks_complete', plan=plan,
        new_audio_or_profile=False, runtime_changed=False, common_phase_RPM_load_or_source_identity=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
