"""Render the finite legal POST candidate and observe EVERY declared native block."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from idle_post_audio_v1.render import voices
from idle_joint_lag_v1.observe import curves, summarize
from idle_joint_lag_v1.checks import run as known

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, parent_manifests={}, renders=[], observations=[])
try:
    plan_path = repo/'research/idle_post_audio_v1_plan.json'; plan = load(plan_path)
    sources = [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
               repo/'tools/idle_post_audio_v1/render.py', repo/'tools/sustain_osc_v1/oracle.py',
               repo/'tools/idle_modal_v1/modal.py', repo/'tools/idle_phase_difference_v1/features.py',
               repo/'tools/idle_positive_power_v1/model.py', repo/'tools/idle_joint_lag_v1/observe.py',
               repo/'tools/idle_joint_lag_v1/checks.py']
    for path in sources:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    lags = np.arange(-1920, 1921, 48); directory = a.out/'known'; directory.mkdir()
    r['known'] = known(directory, lags); print(dict(stage='known', result=r['known']), flush=True)
    tables = {}
    for name in plan['parents']:
        root = a.workspace/'baselines'/name; r['parent_manifests'][name] = sha(root/'manifest.json')
        tables[name] = {v['path']: v['sha256'] for v in load(root/'manifest.json')['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file; digest = sha(path)
        assert digest == tables[name][file]; r['inputs'][str(path)] = digest; return path

    profile_path = parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json')
    law_path = parent('idle_positive_power_v1', 'evidence/observe1/report.json')
    old_path = parent('idle_excitation_moments_v1', 'evidence/observe1/model.json')
    new_path = parent('idle_post_budget_v1', 'evidence/observe1/report.json')
    profile = load(profile_path); law = load(law_path)['observations'][0]['models']['expanded']
    old = load(old_path); new = load(new_path)['allocation']; assert new['generative']
    probability = 3/(np.asarray(new['kappa'])+3)
    assert np.array_equal(probability, new['probability'])
    assert old['kernel_indices'] == [2, 3, 4, 5] and profile['warmup_frames'] == 48000
    r.update(plan=plan, profile_path=str(profile_path), law_path=str(law_path),
             old_path=str(old_path), new_path=str(new_path), new_probability=probability.tolist())
    with np.load(parent('idle_excitation_moments_v1', 'evidence/observe1/training.npz')) as data: sos = data['sos']
    np.save(a.out/'sos.npy', sos)

    def observation(label, audio, section=None, **metadata):
        filtered = np.column_stack([signal.sosfilt(s, audio[:, 0]) for s in sos])
        if section is not None: filtered = filtered[section]
        stats = curves(filtered, lags); path = a.out/(label+'.npz')
        np.savez_compressed(path, filtered=filtered, lags=lags, **stats)
        row = dict(label=label, file=path.name, sha256=sha(path),
                   summary=summarize(stats['normalized'], lags), **metadata)
        r['observations'].append(row)
        return stats

    for name in ['training', 'check']:
        path = parent('idle_excitation_moments_v1', 'evidence/observe1/'+name+'.npz')
        with np.load(path) as data: audio = data['audio']
        sf.write(a.out/('reference_'+name+'.wav'), audio, 48000, subtype='FLOAT')
        stats = observation(name, audio, slice(4800, -4800), source_path=str(path))
        with np.load(parent('idle_joint_lag_v1', 'evidence/observe1/'+name+'.npz')) as prior:
            error = float(abs(stats['normalized']-prior['raw_normalized']).max()); assert error < 1e-9
        r['observations'][-1]['archived_source_curve_error'] = error
    frames = plan['seconds']*48000
    for seed in plan['seeds']:
        main, details, q, events = voices(profile, law, old['probability'], probability, seed, frames, 48000)
        if seed == plan['seeds'][0]:
            sf.write(a.out/'main.wav', main, 48000, subtype='FLOAT'); np.save(a.out/'native_q.npy', q)
        for mode, detail in details.items():
            buses = dict(mix=main+detail, detail=detail)
            row = dict(seed=seed, method=mode, buses={}, events=events)
            for bus, y in buses.items():
                assert np.isfinite(y).all() and abs(y).max() < 1., 'Do not normalize away an unsafe source'
                path = a.out/f'{mode}_{seed}_{bus}.wav'; sf.write(path, y, 48000, subtype='FLOAT')
                actual, rate = sf.read(path, always_2d=True); assert rate == 48000
                if mode in ['static', 'sparse']:
                    tag = '000' if mode == 'static' else '100'
                    frozen = parent('idle_excitation_moments_v1', f'evidence/trial1/{bus}_{tag}_{seed}.wav')
                    assert np.array_equal(actual, sf.read(frozen, always_2d=True)[0]), (mode, seed, bus)
                    if mode == 'static' and bus == 'mix':
                        frozen = parent('idle_texture_v2', f'evidence/trial1/fine_{seed}.wav')
                        assert np.array_equal(actual, sf.read(frozen, always_2d=True)[0])
                row['buses'][bus] = dict(file=path.name, sha256=sha(path), peak=float(abs(actual).max()),
                                        rms_LR=np.sqrt(np.mean(actual**2, axis=0)).tolist())
                if bus == 'mix':
                    # Filter the whole12s first; no repeated filter reset at block boundaries.
                    filtered = np.column_stack([signal.sosfilt(s, actual[:, 0]) for s in sos])
                    for block in range(4):
                        part = filtered[block*144000+4800:(block+1)*144000-4800]
                        stats = curves(part, lags); label = f'{mode}_{seed}_block{block}'; out = a.out/(label+'.npz')
                        np.savez_compressed(out, filtered=part, lags=lags, **stats)
                        r['observations'].append(dict(label=label, file=out.name, sha256=sha(out),
                            seed=seed, method=mode, block=block, audio_file=path.name,
                            summary=summarize(stats['normalized'], lags)))
            r['renders'].append(row)
        print(dict(stage='seed_complete', seed=seed, methods=3, blocks_per_method=4), flush=True)
    r.update(result='finite_POST_idle_audio_pending_listening', runtime_changed=False,
             all_seeds_and_blocks_retained=True, theory_lag_qualified=False, listening_accepted=False,
             source_PCM_used_for_synthesis=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(dict(result=r['result'], renders=len(r['renders']), observations=len(r['observations'])), flush=True)
