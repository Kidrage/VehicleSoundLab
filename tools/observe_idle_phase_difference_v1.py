"""Observe nested low-phase/difference prediction; no sound or runtime changes."""
import argparse
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from idle_phase_difference_v1.features import matrix
from idle_phase_difference_v1.model import fit, assess, predict, decision
from idle_phase_difference_v1.budget import decompose
from idle_phase_difference_v1.checks import run

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, parent_manifests={}, inputs={}, observations=[])
try:
    plan_path = repo/'research/idle_phase_difference_v1_plan.json'
    plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
                 repo/'tools/idle_conditioned_detail_v1/features.py',
                 *sorted((repo/'tools/idle_phase_difference_v1').glob('*.py'))]:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][name.as_posix()] = sha(path)
    r['known'] = run(); save(a.out/'known.json', r['known'])
    print(dict(stage='known', result='passed', details=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name
        r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

    def parent(file):
        root = a.workspace/'baselines/idle_conditioned_detail_v1'
        path = root/file
        assert sha(path) == tables['idle_conditioned_detail_v1'][file]
        r['inputs'][str(path)] = sha(path)
        return path

    old = load(parent('evidence/observe1/report.json'))
    frequencies = np.asarray(old['frequencies_hz'])
    r['frequencies_hz'] = frequencies.tolist()
    r['difference_frequencies_hz'] = [float(frequencies[j]-frequencies[i]) for i, j in [(0, 1), (0, 2), (1, 2)]]
    lags = np.arange(-40, 41)
    for group, seed in [('source', None), ('phase149921', 149921), ('phase277139', 277139), ('phase381611', 381611)]:
        data = {}
        for part in ['train', 'check']:
            suffix = '' if seed is None else '_phase_'+str(seed)
            path = parent(f'evidence/observe1/{part}{suffix}.npz')
            with np.load(path) as archive:
                z, power = archive['phasors'], archive['power']
                features = dict(native=matrix(z, False), expanded=matrix(z))
                assert np.array_equal(features['native'], archive['feature'])
            data[part] = dict(phasors=z, power=power, **features)
        row = dict(group=group, seed=seed, models={}, assessment={}, time_budget={})
        saved = dict(lags_ms=lags)
        for kind in ['native', 'expanded']:
            model = fit(data['train'][kind], data['train']['power'])
            row['models'][kind] = model; row['assessment'][kind] = {}; row['time_budget'][kind] = {}
            reference = np.asarray(model['reference_power'])
            scale = (data['train']['power']/reference).std(axis=0)
            saved[kind+'_scale'] = scale
            for part in ['train', 'check']:
                f, e = data[part][kind], data[part]['power']
                target, prediction = e/reference, predict(model, f)
                row['assessment'][kind][part] = assess(model, f, e)
                terms, stats = decompose(target, prediction, scale, lags)
                assert stats['maximum_closure_error'] < 1e-11
                row['time_budget'][kind][part] = stats
                prefix = kind+'_'+part+'_'
                saved.update({prefix+'feature': f, prefix+'target': target, prefix+'prediction': prediction})
                saved.update({prefix+key: value for key, value in terms.items()})
        before = np.asarray(row['assessment']['native']['check']['mse'])
        after = np.asarray(row['assessment']['expanded']['check']['mse'])
        row['incremental_check_improvement'] = (1-after/before).tolist()
        # Exact reproduction of the existing model is a prerequisite, not a new fit recipe.
        previous = old['model'] if seed is None else next(v['model'] for v in old['phase_controls'] if v['seed'] == seed)
        assert np.allclose(row['models']['native']['coefficients'], previous['coefficients'], atol=1e-12, rtol=0)
        np.savez_compressed(a.out/(group+'.npz'), **saved)
        row.update(file=group+'.npz', sha256=sha(a.out/(group+'.npz')))
        r['observations'].append(row)
        print(dict(group=group, incremental_check_improvement=row['incremental_check_improvement'],
                   lower_bound=row['models']['expanded']['lower_bound']), flush=True)
    r.update(decision(r['observations']))
    r.update(result='all_nested_phase_difference_observations_complete', plan=plan,
             check_used_for_fit=False, waveform_cumulant_budget_proven=False,
             audio_or_runtime_profile_exported=False, runtime_changed=False,
             physical_engine_phase_qualified=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
