"""Complete pre-innovation output budgets; no random sound or new runtime recipe."""
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
from idle_positive_power_v1.model import predict
from idle_wave_budget_v1.response import Fields
from idle_wave_budget_v1.moments import pooled, MOMENTS, TERMS
from idle_wave_budget_v1.checks import run

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, parent_manifests={}, inputs={}, cases=[])
try:
    plan_path = repo/'research/idle_wave_budget_v1_plan.json'; plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
                 repo/'tools/idle_phase_difference_v1/features.py', repo/'tools/idle_positive_power_v1/model.py',
                 *sorted((repo/'tools/idle_wave_budget_v1').glob('*.py'))]:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    known = a.out/'known'; known.mkdir(); r['known'] = run(known)
    print(dict(stage='exact_known_ensembles', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name
        r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file
        digest = sha(path); assert digest == tables[name][file]; r['inputs'][str(path)] = digest
        return path

    profile = load(parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json'))
    power = load(parent('idle_positive_power_v1', 'evidence/observe1/report.json'))
    assert power['future_synthesis_prerequisite']
    law = power['observations'][0]['models']['expanded']
    with np.load(parent('idle_joint_lag_v1', 'evidence/observe1/expectation.npz')) as data:
        h, kappa = data['h'], data['kappa']; old_normalized = data['normalized']
    with np.load(parent('idle_excitation_moments_v1', 'evidence/observe1/training.npz')) as data:
        sos = data['sos']
    reconstructed = []
    for cascade in sos:
        row = []
        for kernel in profile['kernels']:
            impulse = np.zeros(h.shape[2]); impulse[:len(kernel['taps'])] = kernel['taps']
            row.append(signal.sosfilt(cascade, impulse)*kernel['gain'])
        reconstructed.append(row)
    assert np.array_equal(np.asarray(reconstructed), h)
    tail = np.sum(h[:, :, -4096:]**2, axis=2)/np.sum(h*h, axis=2)
    assert tail.max() < 1e-12
    warmup, frames, rate = max(profile['warmup_frames'], h.shape[2]-1), 288000, 48000
    t = (np.arange(warmup+frames)-warmup)/rate
    modal = profile['modal']; frequency = np.asarray(modal['frequencies_hz'])
    angles = 2*np.pi*np.remainder(t[:, None]*frequency, 1.)+np.asarray(modal['initial_phase_LR'])[:, 0]
    main = np.cos(angles)@np.asarray(modal['amplitude_LR'])[:, 0]
    filtered = np.column_stack([signal.sosfilt(s, main) for s in sos])[warmup:]
    phasors = np.exp(1j*angles[:, [1, 2, 4]])
    feature = matrix(phasors, hop=1, trim=0)
    q = predict(law, feature)
    assert np.all(q.min(axis=0) >= law['bounds']['power_lower']) and np.all(q.max(axis=0) <= law['bounds']['power_upper'])
    v = np.ones((warmup+frames, 6)); v[:, 2:] = q
    np.savez_compressed(a.out/'architecture.npz', h=h, kappa=kappa, sos=sos, main=filtered,
                        variance=v, warmup=warmup, frames=frames, rate=rate)
    r.update(profile_sha256=sha(parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json')),
             effective_tail_fraction=tail.tolist(), input_variance_mean=q[warmup:].mean(axis=0).tolist(),
             input_variance_min=q.min(axis=0).tolist(), input_variance_max=q.max(axis=0).tolist())
    lags = np.arange(-1920, 1921, 48); pairs = [(b, c) for b in range(4) for c in range(b, 4)]
    for amount in [0, 1]:
        field = Fields(h, np.ones_like(v) if amount == 0 else v, warmup, frames, kappa, stationary=amount == 0)
        V = field.variances()
        storage = []
        for block in range(2):
            start, stop = block*144000+4800, (block+1)*144000-4800
            mean = filtered[start:stop].mean(axis=0)
            main_variance = ((filtered[start:stop]-mean)**2).mean(axis=0)
            variance = main_variance+V[start:stop].mean(axis=0)
            common = dict(lags=lags, mean=mean, main_variance=main_variance,
                          random_variance=V[start:stop].mean(axis=0), variance=variance,
                          mean_power=(filtered[start:stop]**2+V[start:stop]).mean(axis=0))
            for distribution in ['Gaussian', 'sparse']:
                arrays = dict(common, normalized=np.zeros((10, 81)), covariance=np.zeros((10, 81)),
                              raw=np.zeros((10, 81, 8)), terms=np.zeros((10, 81, 7)))
                storage.append((block, distribution, arrays))
        for pair, (b, c) in enumerate(pairs):
            for li, lag in enumerate(lags):
                C, J = field.pair(b, c, int(lag))
                for block, distribution, arrays in storage:
                    first = block*144000+4800+max(0, -lag)
                    last = (block+1)*144000-4800-max(0, lag)
                    left, right = slice(first, last), slice(first+lag, last+lag)
                    j = J[left] if distribution == 'sparse' else np.zeros(last-first)
                    result = pooled(filtered[left, b], filtered[right, c], V[left, b], V[right, c], C[left], j)
                    denominator = arrays['variance'][b]*arrays['variance'][c]
                    arrays['normalized'][pair, li] = result['cumulant']/denominator
                    arrays['covariance'][pair, li] = result['covariance']/np.sqrt(denominator)
                    arrays['raw'][pair, li] = result['raw']
                    arrays['terms'][pair, li] = [result['terms'][name]/denominator for name in TERMS]
            print(dict(amount=amount, pair=[b, c], lags_complete=81), flush=True)
        for block, distribution, arrays in storage:
            assert np.allclose(arrays['normalized'], arrays['terms'].sum(axis=2), atol=1e-12)
            if amount == 0 and block == 0 and distribution == 'sparse':
                error = float(abs(arrays['normalized']-old_normalized).max())
                assert error < 1e-8, error
                r['original_stationary_full_curve_error'] = error
            label = f'amount{amount}_{distribution}_block{block}'; path = a.out/(label+'.npz')
            np.savez_compressed(path, **arrays)
            late = (abs(lags) >= 384) & (abs(lags) <= 960)
            r['cases'].append(dict(label=label, amount=amount, distribution=distribution, block=block,
                                   file=path.name, sha256=sha(path), mean_power=arrays['mean_power'].tolist(),
                                   late8_to20ms_mean=arrays['normalized'][:, late].mean(axis=1).tolist(),
                                   zero_lag=arrays['normalized'][:, 40].tolist()))
    r.update(result='all_actual_preinnovation_wave_budgets_complete_NO_sound_promotion', plan=plan,
             moment_order=[list(v) for v in MOMENTS], terms=TERMS, mean_centering='ensemble_time_origin_NOT_random_record_estimator',
             generated_random_audio=False, runtime_changed=False, source_or_phase_identified=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
