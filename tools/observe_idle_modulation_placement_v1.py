"""Sample PRE/POST resonance placement with exact PRE benchmark and declared MC error."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from idle_modulation_placement_v1.render import known, powers
from idle_modulation_placement_v1.statistics import jackknife, contrast, exact, LABELS
from idle_wave_budget_v1.response import Fields

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, parent_manifests={}, observations=[])
try:
    plan_path = repo/'research/idle_modulation_placement_v1_plan.json'; plan = load(plan_path)
    sources = [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
               repo/'tools/idle_wave_budget_v1/response.py',
               *sorted((repo/'tools/idle_modulation_placement_v1').glob('*.py'))]
    for path in sources:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    r['known'] = known(); print(dict(stage='known', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name
        r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {row['path']: row['sha256'] for row in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file; assert sha(path) == tables[name][file]
        r['inputs'][str(path)] = sha(path); return path

    profile = load(parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json'))
    with np.load(parent('idle_wave_budget_v1', 'evidence/observe2/architecture.npz')) as archive:
        h, v, sos = archive['h'], archive['variance'], archive['sos']
        warmup, frames = int(archive['warmup']), int(archive['frames'])
    assert frames == 288000 and warmup == 65535
    taps = [np.asarray(k['taps'])*k['gain'] for k in profile['kernels']]
    amplitude = np.sqrt(v)
    reference = np.sum(h*h, axis=(1, 2))
    expected = Fields(h, v, warmup, frames, np.zeros(6)).variances()
    expected = expected.reshape(-1, 48, 4).mean(axis=1)/reference
    target = v[warmup:, 2:].reshape(-1, 48, 4).mean(axis=1)
    samples = []
    for seed in range(64):
        value = powers(seed, taps, amplitude, sos, warmup, frames)/reference
        assert value.shape == (2, 6000, 4) and np.isfinite(value).all()
        samples.append(value)
        if seed % 8 == 7: print(dict(stage='paired_seed', completed=seed+1, total=64), flush=True)
    samples = np.asarray(samples)
    for block in range(2):
        section = slice(block*3000+100, (block+1)*3000-100)
        benchmark = exact(expected[section], target[section]); results = []
        for placement in range(2):
            result = jackknife(samples[:, placement, section], target[section]); results.append(result)
            row = dict(block=block, placement=['pre', 'post'][placement],
                       **{k: v.tolist() for k, v in result.items() if k != 'leave'})
            if placement == 0:
                row['exact'] = benchmark.tolist()
                row['exact_inside_pointwise95'] = ((benchmark >= result['low']) & (benchmark <= result['high'])).tolist()
                row['exact_estimate_abs_error'] = abs(benchmark-result['point']).tolist()
            r['observations'].append(row)
        difference = contrast(*results, 64)
        r.setdefault('paired_post_minus_pre', []).append(dict(block=block, **{k: v.tolist() for k, v in difference.items()}))
        print(dict(stage='block', block=block, mse_pre=results[0]['point'][4:8].tolist(),
                   mse_post=results[1]['point'][4:8].tolist(), mse_family_high=difference['mse_family_high'].tolist()), flush=True)
    path = a.out/'powers.npz'
    np.savez_compressed(path, samples=samples, expected_pre=expected, target=target, reference=reference,
                        seeds=np.arange(64), observation_rate=1000)
    r.update(result='all64_paired_placement_power_observations_complete_NO_timbre_claim',
             data_file=path.name, data_sha256=sha(path), labels=LABELS, plan=plan,
             random_audio_files_generated=False, gaussian_only_NOT_fourth_budget=True,
             all_pointwise_pre_coverage=sum(sum(x.get('exact_inside_pointwise95', [])) for x in r['observations']),
             number_pre_checks=36, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
