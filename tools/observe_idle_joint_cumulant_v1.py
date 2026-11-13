"""Joint idle detail observations; no new synthesis, parameter fit or adoption."""
import argparse, shutil, sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from idle_joint_cumulant_v1.moments import joint, local_normalize, independent_expectation
from idle_joint_cumulant_v1.checks import fixtures, check

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, observations=[], parent_manifests={})
try:
    plan_path = repo / 'research/idle_joint_cumulant_v1_plan.json'
    plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
                 *sorted((repo/'tools/idle_joint_cumulant_v1').glob('*.py'))]:
        name = path.relative_to(repo)
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['sources'][name.as_posix()] = sha(path)
    known = a.out/'known'
    known.mkdir()
    known_data = fixtures()
    for name, data in known_data.items():
        np.savez_compressed(known/(name+'.npz'), **data)
    r['known'] = check(known_data)
    print(dict(stage='known_ensembles', errors={k:v['error'] for k,v in r['known'].items()}), flush=True)
    parents = {}
    for name in ['idle_excitation_moments_v1', 'idle_conditioned_detail_v1']:
        root = a.workspace/'baselines'/name
        parents[name] = (root, {v['path']:v['sha256'] for v in load(root/'manifest.json')['files']})
        r['parent_manifests'][name] = sha(root/'manifest.json')

    def parent(name, file):
        root, table = parents[name]
        path = root/file
        digest = sha(path)
        assert digest == table[file], (name, file)
        r['inputs'][str(path)] = digest
        return path

    def add(label, kind, filtered, **meta):
        row = dict(label=label, kind=kind, frames=len(filtered), **meta,
            raw=joint(filtered), local40ms=joint(local_normalize(filtered, plan['local_power_frames'])))
        r['observations'].append(row)
        return row

    base = 'idle_excitation_moments_v1'
    original = {}
    for name in ['training', 'check']:
        data = np.load(parent(base, 'evidence/observe1/'+name+'.npz'))
        original[name] = data['audio']
        if name == 'training':
            sos = data['sos']
        assert np.array_equal(sos, data['sos'])
        filtered = np.column_stack([signal.sosfilt(s, data['audio'][:,0]) for s in sos])[4800:-4800]
        assert abs(filtered-data['filtered']).max() < 1e-14
        add(name, 'source', filtered, parent_npz=str(parent(base, 'evidence/observe1/'+name+'.npz')))
        spectrum = np.fft.rfft(data['audio'], axis=0)
        for seed in plan['seeds']:
            phase = np.random.default_rng(seed).uniform(-np.pi, np.pi, len(spectrum))
            phase[0] = phase[-1] = 0.
            shifted = np.fft.irfft(spectrum*np.exp(1j*phase[:,None]), n=len(data['audio']), axis=0)
            path = a.out/f'{name}_phase_{seed}.npz'
            np.savez_compressed(path, audio=shifted, phase=phase)
            filtered = np.column_stack([signal.sosfilt(s, shifted[:,0]) for s in sos])[4800:-4800]
            add(f'{name}_phase_{seed}', 'phase', filtered, portion=name, seed=seed, control=path.name)
    for family in ['sparse', 'conditioned50']:
        for seed in plan['seeds']:
            for amount in (plan['amounts'] if family == 'sparse' else [.5]):
                tag = f'{round(amount*100):03d}_{seed}'
                path = parent(base if family == 'sparse' else 'idle_conditioned_detail_v1', 'evidence/trial1/mix_'+tag+'.wav')
                audio, rate = sf.read(path, always_2d=True)
                assert rate == 48000 and audio.shape == (576000, 2)
                filtered = np.column_stack([signal.sosfilt(s, audio[:,0]) for s in sos])
                for block in range(4):
                    first, last = block*144000+4800, (block+1)*144000-4800
                    add(f'{family}_{tag}_{block}', family, filtered[first:last],
                        path=str(path), seed=seed, amount=amount, block=block)
    impulses = np.load(parent(base, 'evidence/observe1/effective_impulses.npz'))
    main = np.column_stack([signal.sosfilt(s, impulses['main'][:,0]) for s in sos])[4800:-4800]
    main_row = add('main', 'main', main)
    model = load(parent(base, 'evidence/observe1/model.json'))
    budget = load(parent(base, 'evidence/observe1/moment_budget.json'))
    kappa = np.zeros(6)
    kappa[model['kernel_indices']] = model['excess_input']
    total = independent_expectation(impulses['impulses'], kappa)
    main_K = np.array(main_row['raw']['cumulant'])
    variance = np.array(budget['model_variance'])
    theoretical = {}
    for amount in plan['amounts']:
        theoretical[str(amount)] = ((main_K+amount**2*total)/np.outer(variance, variance)).tolist()
    assert np.allclose(np.diag(theoretical['1']),
                       np.diag(r['observations'][0]['raw']['normalized']), atol=1e-10)
    np.savez_compressed(a.out/'architecture.npz', sos=sos, kappa=kappa, responses=impulses['impulses'],
        main=impulses['main'], variance=variance, main_cumulant=main_K, independent_cumulant=total)
    pairs = []
    for b in range(4):
        for c in range(b+1, 4):
            row = dict(bands=[b,c], independent_full=theoretical['1'][b][c])
            for transform in ['raw', 'local40ms']:
                detail = []
                for portion in ['training', 'check']:
                    source = next(v for v in r['observations'] if v['label'] == portion)[transform]['normalized'][b][c]
                    controls = [v[transform]['normalized'][b][c] for v in r['observations'] if v['kind']=='phase' and v['portion']==portion]
                    detail.append(dict(portion=portion, source=source, phase_controls=controls,
                        exceeds_every_phase_control=source>max(controls)))
                row[transform] = detail
            row['both_raw_above_controls_and_full_expectation'] = all(v['exceeds_every_phase_control'] and
                v['source']>row['independent_full'] for v in row['raw'])
            pairs.append(row)
    r.update(result='all_joint_idle_observations_complete_NO_sound_promotion', plan=plan,
        theoretical_raw=theoretical, pairs=pairs, runtime_changed=False, new_audio_or_profile=False,
        source_identity_or_RPM_qualified=False)
    print(dict(observations=len(r['observations']), pairs=pairs), flush=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
