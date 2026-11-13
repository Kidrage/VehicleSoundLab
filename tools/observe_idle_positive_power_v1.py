"""Fit positive sample-power models and predict exact averaged band powers."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from research_archive_v1 import load, save, sha
from idle_phase_difference_v1.features import matrix
from idle_phase_difference_v1.budget import decompose
from idle_positive_power_v1.model import fit, predict, average, assess
from idle_positive_power_v1.checks import run

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, parent_manifests={}, inputs={}, observations=[])
try:
    plan_path = repo/'research/idle_positive_power_v1_plan.json'; plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
                 repo/'tools/idle_phase_difference_v1/features.py', repo/'tools/idle_phase_difference_v1/budget.py',
                 *sorted((repo/'tools/idle_positive_power_v1').glob('*.py'))]:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    r['known'] = run(); save(a.out/'known.json', r['known'])
    print(dict(stage='known', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name
        r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file
        digest = sha(path); assert digest == tables[name][file]
        r['inputs'][str(path)] = digest
        return path

    old = load(parent('idle_phase_difference_v1', 'evidence/observe2/report.json'))
    bands = old['plan']['observation']
    band_edges = [[1200, 2200], [2200, 4000], [4000, 8000], [8000, 14000]]
    sos = np.asarray([signal.butter(4, band, btype='bandpass', fs=48000, output='sos') for band in band_edges])
    audio = {}
    for part in ['train', 'check']:
        with np.load(parent('idle_conditioned_detail_v1', f'evidence/observe1/{part}.npz')) as archive:
            audio[part] = archive['audio']
    lags = np.arange(-40, 41)
    for prior in old['observations']:
        group, seed = prior['group'], prior['seed']; data = {}; saved = dict(lags_ms=lags, sos=sos)
        for part in ['train', 'check']:
            x = audio[part]
            if seed is not None:
                spectrum = np.fft.rfft(x, axis=0)
                phase = np.random.default_rng(seed).uniform(-np.pi, np.pi, len(spectrum)); phase[0] = phase[-1] = 0
                x = np.fft.irfft(spectrum*np.exp(1j*phase[:, None]), n=len(x), axis=0)
            suffix = '' if seed is None else '_phase_'+str(seed)
            with np.load(parent('idle_conditioned_detail_v1', f'evidence/observe1/{part}{suffix}.npz')) as archive:
                z, old_power = archive['phasors'], archive['power']
            filtered = np.column_stack([signal.sosfilt(s, x[:, 0]) for s in sos])[12000:-12000]
            power = filtered**2
            assert np.array_equal(average(power), old_power)
            data[part] = dict(power=power, native=matrix(z, False, hop=1), expanded=matrix(z, hop=1))
            saved[part+'_filtered'] = filtered
            saved[part+'_power'] = old_power
        row = dict(group=group, seed=seed, models={}, assessment={}, time_budget={})
        for kind in ['native', 'expanded']:
            model = fit(data['train'][kind], data['train']['power'])
            row['models'][kind] = model; row['assessment'][kind] = {}; row['time_budget'][kind] = {}
            reference = np.asarray(model['reference_power'])
            target_train = average(data['train']['power'])/reference
            scale = target_train.std(axis=0); saved[kind+'_scale'] = scale
            for part in ['train', 'check']:
                target = average(data[part]['power'])/reference
                sample_prediction = predict(model, data[part][kind])
                prediction = average(sample_prediction)
                assessment = assess(target, prediction)
                assessment['sample_minimum_prediction'] = sample_prediction.min(axis=0).tolist()
                assessment['sample_maximum_prediction'] = sample_prediction.max(axis=0).tolist()
                row['assessment'][kind][part] = assessment
                terms, stats = decompose(target, prediction, scale, lags)
                row['time_budget'][kind][part] = stats
                prefix = kind+'_'+part+'_'
                saved[prefix+'prediction'] = prediction; saved[prefix+'target'] = target
                saved.update({prefix+key: value for key, value in terms.items()})
            print(dict(group=group, model=kind, converged=model['converged'],
                       gradients=[v['gradient_infinity'] for v in model['fits']]), flush=True)
        before = np.asarray(row['assessment']['native']['check']['mse'])
        after = np.asarray(row['assessment']['expanded']['check']['mse'])
        old_before = np.asarray(prior['assessment']['native']['check']['mse'])
        row['incremental_check_improvement'] = (1-after/before).tolist()
        row['check_improvement_over_old_native_OLS'] = (1-after/old_before).tolist()
        row['old_native_OLS_check_mse'] = old_before.tolist()
        row['old_expanded_OLS_check_mse'] = prior['assessment']['expanded']['check']['mse']
        np.savez_compressed(a.out/(group+'.npz'), **saved)
        row.update(file=group+'.npz', sha256=sha(a.out/(group+'.npz')))
        r['observations'].append(row)
    real = r['observations'][0]
    improvements = np.asarray(real['incremental_check_improvement'])
    controls = np.asarray([v['incremental_check_improvement'] for v in r['observations'][1:]])
    supported = (improvements > 0) & (np.asarray(real['check_improvement_over_old_native_OLS']) > 0) & np.all(improvements > controls, axis=0)
    eligible = all(m['converged'] and m['full_rank'] and m['bounds']['finite_normal_bounds'] for m in real['models'].values())
    r.update(result='all_positive_sample_power_models_observed', plan=plan, bands_hz=band_edges,
             frequencies_hz=old['frequencies_hz'], supported_bands=supported.tolist(),
             future_synthesis_prerequisite=bool(eligible and supported.sum() >= 3),
             check_used_for_fit=False, waveform_budget_proven=False,
             audio_or_runtime_profile_exported=False, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
