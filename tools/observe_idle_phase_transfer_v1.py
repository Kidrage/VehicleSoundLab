"""All180s of the frozen idle power law, contrasted with its recorded-phase inputs."""
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
from idle_phase_transfer_v1.measure import phasors, observe, serial, known

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, parent_manifests={}, source_observations=[], runtime=[])
try:
    plan_path = repo/'research/idle_phase_transfer_v1_plan.json'; plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
                 repo/'tools/idle_phase_transfer_v1/measure.py', repo/'tools/idle_phase_difference_v1/features.py',
                 repo/'tools/idle_positive_power_v1/model.py']:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    r['known'] = known(); print(dict(stage='known', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        path = a.workspace/'baselines'/name/'manifest.json'; r['parent_manifests'][name] = sha(path)
        tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file; digest = sha(path); assert digest == tables[name][file]
        r['inputs'][str(path)] = digest; return path

    profile_path = parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json')
    law_path = parent('idle_positive_power_v1', 'evidence/observe1/report.json')
    profile = load(profile_path); law = load(law_path)['observations'][0]['models']['expanded']
    r.update(plan=plan, profile_path=str(profile_path), law_path=str(law_path))
    source_q = []
    for part in ['train', 'check']:
        path = parent('idle_conditioned_detail_v1', 'evidence/observe1/'+part+'.npz')
        with np.load(path) as data: z = data['phasors'][12000:-12000]
        q, values = observe(z, law); source_q.append(q)
        output = a.out/('source_'+part+'.npz'); np.savez_compressed(output, phasors=z, q=q,
            q_mean1ms=q.reshape(-1, 48, 4).mean(axis=1), **values)
        r['source_observations'].append(dict(part=part, path=str(path), file=output.name, sha256=sha(output), **serial(values)))
    with np.load(parent('idle_positive_power_v1', 'evidence/observe1/source.npz')) as prior:
        errors = [float(abs(source_q[i].reshape(-1, 48, 4).mean(axis=1)-prior['expanded_'+part+'_prediction']).max())
                  for i, part in enumerate(['train', 'check'])]
        assert max(errors) < 1e-12; r['source_previous_prediction_errors'] = errors
    oldq = np.load(parent('idle_post_audio_v1', 'evidence/render1/native_q.npy'))
    blocks = []; summaries = []; first_q = []
    for block in range(60):
        z = phasors(profile, block*144000, 144000); q, values = observe(z, law)
        summaries.append(values); blocks.append(q.reshape(-1, 48, 4).mean(axis=1))
        if block < 4: first_q.append(q)
        r['runtime'].append(dict(block=block, start_seconds=block*3, **serial(values)))
        if block % 10 == 9: print(dict(stage='runtime', blocks=block+1, total=60), flush=True)
    first = np.concatenate(first_q); r['first12s_previous_q_error'] = float(abs(first-oldq).max())
    assert r['first12s_previous_q_error'] < 1e-12
    # Full moments aggregate equal-size native blocks, not statistics of averaged1ms q.
    means = np.array([v['mean'] for v in summaries]); second = np.array([v['second'] for v in summaries])
    fullmean = means.mean(axis=0); firstmean = means[:4].mean(axis=0)
    circular = np.array([v['circular'] for v in summaries])
    full = dict(mean=fullmean.tolist(), second=second.mean(axis=0).tolist(),
                covariance=(second.mean(axis=0)-np.outer(fullmean, fullmean)).tolist(),
                circular_real_imag=np.column_stack((circular.mean(axis=0).real, circular.mean(axis=0).imag)).tolist(),
                resultant=abs(circular.mean(axis=0)).tolist())
    f = np.asarray(profile['modal']['frequencies_hz'])[[1, 2, 4]]; delta = float(f[2]-f[1]-f[0])
    r.update(full180s=full, first12s_mean=firstmean.tolist(),
             runtime_block_mean_min=means.min(axis=0).tolist(), runtime_block_mean_max=means.max(axis=0).tolist(),
             block_q_power_db_relative_first12=(10*np.log10(means/firstmean)).tolist(),
             detuning_hz=delta, closure_period_seconds=1/abs(delta), closure_advance_cycles_180s=delta*180,
             physical_engine_or_RPM_claim=False, runtime_changed=False, audio_generated=False)
    output = a.out/'runtime.npz'; np.savez_compressed(output, q_mean1ms=np.concatenate(blocks),
        block_means=means, block_second=second, block_quantiles=np.array([v['quantiles'] for v in summaries]),
        block_feature_means=np.array([v['feature_mean'] for v in summaries]), block_circular=circular,
        first12s_mean=firstmean, full_mean=fullmean)
    r.update(result='all180s_power_phase_transfer_observed_NO_recipe_change', data_file=output.name, data_sha256=sha(output))
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(dict(result=r['result'], detuning_hz=r.get('detuning_hz'),
           period_seconds=r.get('closure_period_seconds'), mean_min=r.get('runtime_block_mean_min'),
           mean_max=r.get('runtime_block_mean_max')), flush=True)
