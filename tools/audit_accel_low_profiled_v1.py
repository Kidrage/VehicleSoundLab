"""Independently check exact linear elimination, native waves and every track."""
import argparse
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
from scipy.linalg import lstsq
from research_archive_v1 import load, save, sha
from native_chirp_audit_v1.wave import near, audit_wave
from native_chirp_audit_v1.temporal import audit_temporal, audit_predictions

a.out.mkdir(parents=True, exist_ok=False)
for name in ['tools/audit_accel_low_profiled_v1.py', 'tools/native_chirp_audit_v1/wave.py',
             'tools/native_chirp_audit_v1/temporal.py']:
    dest = a.out / 'exact_sources' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / name, dest)
r = dict(result='running', waveforms=0, lines=0, maximum_waveform_error=0.,
         maximum_support_error=0., maximum_left_normal_equation=0.,
         maximum_reduced_optimality_error=0., maximum_phase_arithmetic_error=0., summaries=[])


def conditional_residual(x, nominal, parameters, w, t):
    """Separate complex-exponential design and SVD conditional solve."""
    m = len(nominal)
    phase = t[:, None] * (nominal + parameters[:m]) + .5 * t[:, None] ** 2 * parameters[m:]
    z = np.exp(2j * np.pi * phase)
    design = np.column_stack((z.real, z.imag, np.ones(len(t))))
    matrix = w[:, None] * design
    c = lstsq(matrix, w * x, lapack_driver='gelsd')[0]
    return matrix @ c - w * x


def wave(path, original_path, row, inv, initial, plan):
    z, old = np.load(path), np.load(original_path)
    assert np.array_equal(z['audio'], old['audio'])
    out = audit_wave(z, row, plan)
    r['waveforms'] += 1
    r['lines'] += out['lines']
    r['maximum_waveform_error'] = max(r['maximum_waveform_error'], out['waveform_error'])
    r['maximum_support_error'] = max(r['maximum_support_error'], out['support_error'])
    m = len(row['lines'])
    if not m:
        assert len(inv['bin']) == 0 or len(inv['bin']) > 64
        return
    assert row['nonlinear_parameter_count'] == 2 * m
    assert row['eliminated_linear_parameter_count'] == 2 * m + 1
    near(z['nominal'], np.array(inv['bin']) * 4)
    near(z['initial'][m:2*m], np.clip(initial['initial_chirp'], -500+1e-6, 500-1e-6))
    near(z['reduced_initial'], z['initial'][:2*m], 0)
    near(z['reduced_parameters'], z['parameters'][:2*m], 0)
    for k, line in enumerate(row['lines']):
        assert (line['native_inventory_index'], line['native_bin'], line['native_peak_hz']) == (k, inv['bin'][k], inv['hz'][k])
    n = len(z['audio'])
    t = np.arange(n) / 48000 - n / 96000
    w = np.sqrt((.5 - .5 * np.cos(2 * np.pi * np.arange(n) / n)) / n)
    p0, nominal = z['parameters'], z['nominal']
    phase = 2*np.pi*(t[:, None]*(nominal+p0[:m]) + .5*t[:, None]**2*p0[m:2*m])
    co, si = np.cos(phase), np.sin(phase)
    design = np.column_stack((co, si, np.ones(n)))
    c = p0[2*m:]
    # At each final reduced point the nuisance coefficients must still minimize
    # left LS. Check normal equations as well as an independent SVD residual.
    e = w * (design @ c - z['audio'][:, 0])
    normal = (w[:, None]*design).T @ e
    r['maximum_left_normal_equation'] = max(r['maximum_left_normal_equation'], near(normal, np.zeros(2*m+1), 1e-11))
    near(e, conditional_residual(z['audio'][:, 0], nominal, p0[:2*m], w, t), 1e-11)
    motion = -si*c[:m] + co*c[m:2*m]
    direct = np.column_stack((w[:, None]*(2*np.pi*t[:, None])*motion,
                              w[:, None]*(np.pi*t[:, None]**2)*motion))
    gradient = direct.T @ e
    reduced = p0[:2*m]
    lower, upper = z['lower'][:2*m], z['upper'][:2*m]
    scaling = np.where(gradient < 0, upper-reduced, np.where(gradient > 0, reduced-lower, 1.))
    optimality = float(np.max(abs(gradient*scaling)))
    r['maximum_reduced_optimality_error'] = max(r['maximum_reduced_optimality_error'], near(optimality, row['optimality'], 1e-10))


try:
    report = load(a.input / 'report.json')
    assert report['result'] == 'all48_exact_profiled_native_fits_and_temporal_checks_complete'
    for name, h in report['sources'].items():
        assert sha(a.input / 'exact_sources' / name) == h == sha(repo / name)
    parent = a.workspace / 'references/analysis/accel_low_fit_v1/observe2'
    parent_report = load(parent / 'report.json')
    parent_audit = load(parent.parent / 'audit1/report.json')
    assert parent_audit['result'] == 'all_known_and48_native_waves_initials_tracks_phase_reports_predictions_verified'
    assert parent_audit['input_report_sha256'] == sha(parent/'report.json') == report['parent_report_sha256']
    for name, h in report['input_hashes'].items():
        assert sha(Path(name)) == h
    fit_plan = load(repo/'research/accel_chirp_v1_plan.json')
    link_plan = load(repo/'research/low_chirp_v1_plan.json')
    control = np.load(a.input/'projection_control.npz')
    x, nominal, point, w, t = [control[k] for k in ['audio', 'nominal', 'parameters', 'weight', 'time']]
    rng = np.random.default_rng(349117)
    expected_x = np.cos(2*np.pi*(t[:, None]*[76.3,147.7,300.2]+.5*t[:, None]**2*[13.,-5.,11.])+[.2,.4,-.8])@[.2,.07,.1] + .007*rng.normal(size=len(t))
    near(x, expected_x, 0)
    base = conditional_residual(x, nominal, point, w, t)
    near(base, control['QR_residual'], 1e-12)
    near(base, control['SVD_residual'], 1e-12)
    numeric = []
    for k in range(6):
        step = np.zeros(6)
        step[k] = 1e-5
        numeric.append((conditional_residual(x, nominal, point+step, w, t)-conditional_residual(x, nominal, point-step, w, t))/2e-5)
    numeric = np.column_stack(numeric)
    r['independent_SVD_Jacobian_error'] = near(numeric, control['analytic'], 1e-8)
    near(numeric, control['numeric'], 1e-8)
    assert np.linalg.norm(base) > 0
    known = load(parent/'controls.json')
    rows = load(a.input/'known/rows.json')
    assert len(rows) == 12
    for i, row in enumerate(rows):
        wave(a.input/'known'/f'tile_{i}.npz', parent/'known'/f'tile_{i}.npz', row,
             known['inventories'][i], known['initialization'][i], fit_plan)
        assert row['success'] and len(row['lines']) == 10 and all(v['eligible'] for v in row['lines'])
        assert max(abs(v['frequency_hz']-f) for v, f in zip(row['lines'], known['truth'][i]['frequency_hz'])) < .06
        assert max(abs(v['chirp_hz_per_second']-q) for v, q in zip(row['lines'], known['truth'][i]['q_hzs'])) < .15
        z = np.load(a.input/'known'/f'tile_{i}.npz')
        assert np.linalg.norm(z['residual'])/np.linalg.norm(z['audio']) < 1e-5
    linked = load(a.input/'known/temporal.json')
    value = audit_temporal(rows, linked, link_plan)
    assert value['tracks'] == 10 and all(len(v['windows']) == 12 for v in linked['tracks'])
    r['maximum_phase_arithmetic_error'] = value['maximum_phase_arithmetic_error']
    counters = load(a.input/'known/counterexamples.json')
    assert counters.keys() == known['counterexamples'].keys()
    for name, row in counters.items():
        case = known['counterexamples'][name]
        wave(a.input/'known'/(name+'.npz'), parent/'known'/(name+'.npz'), row, case['inventory'], case['initialization'], fit_plan)
        if name == 'missing_low_with_neighbor':
            assert not next(v for v in row['lines'] if v['nominal_hz']==180)['eligible']
    for name in parent_report['plan']['segments']:
        initial = load(parent/name/'initialization.json')
        rows, old = load(a.input/name/'fits.json'), load(parent/name/'fits.json')
        assert len(rows) == len(old) == len(initial['inventories'])
        for i, row in enumerate(rows):
            assert row['tile'] == i
            for key in ['ratio', 'guide_supported']:
                assert row[key] == old[i][key]
            assert row['original_success'] == old[i]['success'] and row['original_cost'] == old[i]['cost']
            wave(a.input/name/f'tile_{i:02d}.npz', parent/name/f'tile_{i:02d}.npz', row,
                 initial['inventories'][i], initial['initial'][i], fit_plan)
        linked = load(a.input/name/'temporal.json')
        predicted = load(a.input/name/'predictions.json')
        value = audit_temporal(rows, linked, link_plan)
        pred = audit_predictions(rows, linked, predicted)
        r['maximum_phase_arithmetic_error'] = max(r['maximum_phase_arithmetic_error'], value['maximum_phase_arithmetic_error'])
        summary = dict(segment=name, windows=len(rows), successful=sum(v['success'] for v in rows),
            local_lines=sum(len(v['lines']) for v in rows), eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
            low_tracks_atleast5=sum(v['frequencies_hz'][0]<200 and len(v['windows'])>=5 for v in linked['tracks']),
            compared_low_tracks=pred['compared_low_tracks'])
        assert summary == next(v for v in report['observations'] if v['segment']==name)
        r['summaries'].append(dict(**summary, original_successful=sum(v['success'] for v in old),
            newly_successful=[i for i,v in enumerate(rows) if v['success'] and not old[i]['success']],
            newly_failed=[i for i,v in enumerate(rows) if not v['success'] and old[i]['success']],
            failed_windows=[i for i,v in enumerate(rows) if not v['success']],
            lower_cost_windows=[i for i,v in enumerate(rows) if v['cost']<old[i]['cost']],
            longest_low_track=max((len(v['windows']) for v in linked['tracks'] if v['frequencies_hz'][0]<200), default=0)))
    for filename, count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        table = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(table)==count
        for name,h in table.items():
            assert sha(repo/name)==h
    r.update(result='all_profiled_controls_left_LS_reduced_gradient_64native_waves_tracks_predictions_verified',
             input_report_sha256=sha(a.input/'report.json'), parent_audit_sha256=sha(parent.parent/'audit1/report.json'),
             C_H_unchanged=612, old_voices_unchanged=67, optimizer_global_convergence_verified=False,
             no_new_audio_or_profile=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print({key:r[key] for key in ['result','waveforms','lines','maximum_waveform_error','maximum_reduced_optimality_error','summaries']})
