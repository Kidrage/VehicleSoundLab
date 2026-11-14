"""Known controls followed by frozen-source stereo phase-coordinate evidence."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--stage', choices=['known', 'real'], required=True)
    p.add_argument('--known', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import ndtri
    from scipy.stats import qmc
    from relative_phase_v1.coordinates import encode, phases, decode
    from relative_phase_v1.profile import compile_rows
    from relative_phase_v1.observe import phase_budget
    from radial_copula_v1.latent import independent_draws
    from radial_copula_v1.observe import describe, json_summary
    from radial_copula_v1.quantiles import integral
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=a.stage, sources={}, inputs={}, cases=[])
    try:
        sources = ['research/relative_phase_v1_plan.json', 'tools/run_relative_phase_v1.py',
                   'tools/relative_phase_v1/coordinates.py', 'tools/relative_phase_v1/profile.py',
                   'tools/relative_phase_v1/observe.py', 'tools/radial_copula_v1/latent.py',
                   'tools/radial_copula_v1/observe.py', 'tools/radial_copula_v1/quantiles.py']
        for name in sources:
            path = a.out/'exact_sources'/name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path); report['sources'][name] = sha(path)
        plan = load(repo/'research/relative_phase_v1_plan.json'); gates = plan['checks']
        def consume(path):
            report['inputs'][str(path)] = sha(path)
            return path
        def fit(label, z):
            folder = a.out/label; folder.mkdir()
            values = np.stack([z.real, z.imag], axis=-1).reshape(len(z), -1)
            model, training = compile_rows(values)
            coordinates, _ = encode(z)
            reconstruction = abs(z)*np.exp(1j*phases(coordinates))
            error = float(abs(reconstruction-z).max())
            assert error <= gates['source_coordinate_roundtrip_FS']
            assert abs(integral(model['amplitude'], 2)-model['target_amplitude_second']).max() < 2e-12
            np.savez_compressed(folder/'profile.npz', **model)
            np.savez_compressed(folder/'training.npz', **training)
            row = dict(label=label, profile_sha256=sha(folder/'profile.npz'),
                       training_sha256=sha(folder/'training.npz'),
                       coordinate_roundtrip_error_FS=error)
            return folder, model, row
        if a.stage == 'known':
            t = np.arange(plan['known_rows'])/plan['known_rows']; h = np.arange(1, 9)
            amp = .1*(1+.15*np.sin(2*np.pi*t[:, None]+.2*h))
            common = .7*np.sin(2*np.pi*t[:, None]+.13*h)
            relative = .6*np.sin(4*np.pi*t[:, None]+.3*h)
            steady = np.broadcast_to(.1*np.exp(1j*.23*h), (len(t), len(h)))
            fixtures = {
                'identical_stereo': np.stack([amp*np.exp(1j*common)]*2, axis=-1),
                'fixed_relative': np.stack([steady, 1.4*steady*np.exp(-.7j)], axis=-1),
                'common_PM': np.stack([.1*np.exp(1j*common)]*2, axis=-1),
                'relative_PM': .1*np.exp(1j*np.stack([common+.5*relative, common-.5*relative], axis=-1)),
                'opposed_AM': np.stack([amp, .2-amp], axis=-1).astype(complex),
                'wrap': .1*np.exp(1j*np.stack([3.12+.4*common+.5*relative,
                                               3.12+.4*common-.5*relative], axis=-1)),
                'silence': np.zeros((len(t), len(h), 2), dtype=complex)}
            fixtures['rotated'] = fixtures['wrap']*np.exp(1j*.97)
            fixtures['swapped'] = fixtures['wrap'][..., ::-1]
            for label in plan['known']:
                z = fixtures[label]; folder, model, row = fit(label, z)
                normal = np.random.Generator(np.random.PCG64(1)).standard_normal((4096, len(model['rho'])+model['basis'].shape[0]))
                amplitude, phase = decode(model, independent_draws(model, normal))
                if label in ('common_PM', 'relative_PM', 'wrap', 'rotated', 'swapped'):
                    assert abs(amplitude-.1).max() < 2e-14
                if label in ('identical_stereo', 'common_PM', 'opposed_AM'):
                    assert abs(np.angle(np.exp(1j*(phase[..., 0]-phase[..., 1])))).max() < 2e-12
                if label == 'fixed_relative':
                    assert abs(np.angle(np.exp(1j*(phase[..., 0]-phase[..., 1]-.7)))).max() < 2e-12
                if label == 'silence':
                    assert np.count_nonzero(amplitude) == 0
                row['generated_control_passed'] = True
                report['cases'].append(row)
            original = phase_budget(abs(fixtures['wrap']), np.angle(fixtures['wrap']))
            for name, conjugate in [('rotated', False), ('swapped', True)]:
                measured = phase_budget(abs(fixtures[name]), np.angle(fixtures[name]))
                assert all(np.allclose(measured[k], v.conj() if conjugate else v, atol=2e-14, rtol=0)
                           for k, v in original.items())
            report['source_rotation_and_channel_swap_invariants'] = True
            report['result'] = 'relative_phase_known_controls_passed'
        else:
            known = load(consume(a.known/'report.json')); audit = load(consume(a.known_audit/'report.json'))
            assert known['result'] == 'relative_phase_known_controls_passed'
            assert audit['result'] == 'independent_relative_phase_audit_passed'
            assert audit['producer_sha256'] == sha(a.known/'report.json')
            assert known['sources'] == report['sources']
            parent = a.workspace/'baselines/radial_copula_v1'
            assert sha(consume(parent/'manifest.json')) == load(repo/'research/radial_copula_v1_summary.json')['manifest_sha256']
            entries = {r['path']: r['sha256'] for r in load(parent/'manifest.json')['files']}
            def frozen(name):
                path = consume(parent/name); assert sha(path) == entries[name]
                return path
            prior = load(frozen('evidence/real2/report.json'))
            errors = {'old_fixed': [], 'old_absolute': [], 'relative': [], 'new_fixed': []}
            old_CV, new_CV, source_CV = [], [], []
            for old in prior['cases']:
                label = old['label']; root = old['root_hz']
                raw = np.load(frozen(f'evidence/real2/{label}/training.npz'))['source_rows']
                q = raw.reshape(len(raw), -1, 2, 2); z = q[..., 0]+1j*q[..., 1]
                folder, model, row = fit(label, z)
                original_model = np.load(frozen(f'evidence/real2/{label}/profile.npz'))
                assert np.array_equal(model['amplitude'], original_model['amplitude'])
                assert np.array_equal(model['fixed_phase'], original_model['fixed_phase'])
                source = describe(abs(z), np.angle(z), root, plan['bands_Hz'])
                row.update(root_hz=root, source=json_summary(source), QMC=[])
                source_budget = phase_budget(abs(z), np.angle(z))
                relative_means, fixed_means, cvs = [], [], []
                for seed in plan['QMC']['seeds']:
                    uniform = qmc.Sobol(d=model['basis'].shape[0]+len(model['rho']), scramble=True, seed=seed).random_base2(plan['QMC']['power'])
                    normal = ndtri(uniform)
                    amp, phase = decode(model, independent_draws(model, normal))
                    measured = describe(amp, phase, root, plan['bands_Hz'])
                    fixed = describe(amp, np.broadcast_to(model['fixed_phase'], amp.shape), root, plan['bands_Hz'])
                    budget = phase_budget(amp, phase)
                    mean_error = float(abs(10*np.log10(measured['mean']/source['mean'])).max())
                    assert mean_error < gates['QMC_mean_power_dB']
                    output = folder/f'QMC_{seed}.npz'
                    np.savez_compressed(output, **{'relative_'+k: v for k, v in measured.items()},
                                        **{'fixed_'+k: v for k, v in fixed.items()},
                                        **{'budget_'+k: v for k, v in budget.items()},
                                        **{'source_budget_'+k: v for k, v in source_budget.items()})
                    row['QMC'].append(dict(seed=seed, sha256=sha(output),
                        uniform_bytes_sha256=hashlib.sha256(uniform.tobytes()).hexdigest(),
                        maximum_mean_power_error_dB=mean_error,
                        relative=json_summary(measured), fixed=json_summary(fixed)))
                    relative_means.append(measured['complex_coherence']); fixed_means.append(fixed['complex_coherence']); cvs.append(measured['CV'])
                old_fixed = np.mean([r['fixed']['complex_coherence'] for r in old['QMC']], axis=0)
                old_absolute = np.mean([r['joint']['complex_coherence'] for r in old['QMC']], axis=0)
                complex_array = lambda x: x[..., 0]+1j*x[..., 1]
                for name, value in [('old_fixed', complex_array(old_fixed)), ('old_absolute', complex_array(old_absolute)),
                                    ('relative', np.mean(relative_means, axis=0)), ('new_fixed', np.mean(fixed_means, axis=0))]:
                    errors[name].extend(abs(value-source['complex_coherence']).tolist())
                old_CV.extend(np.mean([r['joint']['CV'] for r in old['QMC']], axis=0)); new_CV.extend(np.mean(cvs, axis=0)); source_CV.extend(source['CV'])
                report['cases'].append(row); save(a.out/'report.json', report)
                print('PASS frozen source coordinates and power', label, flush=True)
            report['stereo_comparison'] = dict(mean_absolute_complex_error={k: float(np.mean(v)) for k, v in errors.items()},
                per_coordinate_errors=errors,
                relative_better_than_old_fixed=int(np.sum(np.array(errors['relative'])<errors['old_fixed'])),
                relative_better_than_old_absolute=int(np.sum(np.array(errors['relative'])<errors['old_absolute'])),
                coordinates=len(errors['relative']))
            report['CV_error_L2'] = dict(old_radial=float(np.linalg.norm(np.array(old_CV)-source_CV)),
                                        relative_phase=float(np.linalg.norm(np.array(new_CV)-source_CV)))
            report['runtime_or_timbre_adopted'] = False
            report['result'] = 'six_source_relative_phase_evidence_ready'
        save(a.out/'report.json', report)
        print(report['result'], flush=True)
    except BaseException as exc:
        report.update(result='failed', error=repr(exc)); save(a.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
