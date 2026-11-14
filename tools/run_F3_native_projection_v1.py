"""Known-controlled native harmonic/remainder/cross budgets for six fixed anchors."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from native_projection_v1.projection import Projector, inverse_phase
    from native_projection_v1.budget import measure
    from native_projection_v1.controls import fixtures

    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, known=[], cases=[])

    def source(path):
        r['inputs'][str(path)] = sha(path)
        return path

    def execute(label, audio, phase, projector, extra=None):
        folder = a.out/label
        folder.mkdir()
        h, rem, coef, metrics = projector.split(audio)
        assert metrics['max_reconstruction_FS'] <= gates['projection_reconstruction_FS']
        assert metrics['max_normal_residual_FS'] <= gates['normal_residual_FS']
        assert np.max(abs(np.array(metrics['global_HR_FS2']))) <= gates['global_HR_FS2']
        # audio may hold nine stereo chunks as18 columns; fit simultaneously,
        # but retain each stereo decomposition and window budget independently.
        count = audio.shape[1]//2
        budgets = [measure(audio[:, 2*i:2*i+2], h[:, 2*i:2*i+2], rem[:, 2*i:2*i+2], spec) for i in range(count)]
        values = dict(audio=audio, phase=phase, harmonic=h, remainder=rem, coefficients=coef)
        if extra:
            values.update(extra)
        for key in budgets[0]:
            values[key] = np.stack([b[key] for b in budgets])
        np.savez_compressed(folder/'arrays.npz', **values)
        error = 0
        for b in budgets:
            total = b['P_harmonic']+b['P_remainder']+b['cross_HR_RH']
            diff = abs(total-b['P_full'])
            assert np.all(diff <= gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(b['P_full']))
            error = max(error, float(diff.max()))
        metrics.update(label=label, stereo_inputs=count, budget_identity_max_FS2=error,
                       data_sha256=sha(folder/'arrays.npz'))
        return metrics, h, rem

    try:
        names = ['tools/run_F3_native_projection_v1.py', 'tools/research_archive_v1.py',
                 'research/F3_native_projection_v1_plan.json']
        names += [p.relative_to(repo).as_posix() for p in (repo/'tools/native_projection_v1').glob('*.py')]
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        plan = load(repo/'research/F3_native_projection_v1_plan.json')
        gates, spec = plan['gates'], plan['measurement']
        known = fixtures(plan['known_before_source'])
        static_projector = Projector(known[0]['phase'], minimum_diagonal=gates['minimum_QR_diagonal'])
        for case in known:
            projector = static_projector if case['name'] != 'rising_inverse_clock' else Projector(case['phase'])
            extras = {k: v for k, v in case.items() if k not in ['name', 'phase', 'full']}
            row, h, rem = execute('known_'+case['name'], case['full'], case['phase'], projector, extras)
            if 'truth_H' in case:
                error = max(float(abs(h-case['truth_H']).max()), float(abs(rem-case['truth_R']).max()))
                gate = gates['known_chirp_inverse_wave_FS'] if case['name'] == 'rising_inverse_clock' else gates['known_exact_wave_FS']
                assert error <= gate, (case['name'], error)
                row['truth_wave_error_FS'] = error
            if 'exact_analytic_phase' in case:
                error = float(abs(case['phase']-case['exact_analytic_phase']).max())
                assert error <= gates['known_phase_inverse_cycles']
                row['phase_inverse_error_cycles'] = error
            if 'noise' in case:
                nh, nr, _, _ = static_projector.split(case['noise'])
                error = max(float(abs(h-case['deterministic_H']-nh).max()), float(abs(rem-nr).max()))
                assert error <= gates['known_exact_wave_FS']
                expected = .035**2*(1-static_projector.design.shape[1]/len(rem))
                error_power = float(abs(np.mean(rem*rem, axis=0)/expected-1).max())
                assert error_power <= gates['white_noise_retained_power_relative']
                row.update(noise_linear_error_FS=error, retained_noise_power_relative_error=error_power,
                           expected_finite_noise_remainder_power_FS2=expected)
            r['known'].append(row)
            save(a.out/'report.json', r)
            print('PASS known', case['name'], flush=True)
        r['known_controls_passed_before_source'] = True
        del static_projector, known, projector
        parent = a.workspace/'baselines/F3_local_detail_budget_v1'
        manifest = load(source(parent/'manifest.json'))
        expected = {row['path']: row['sha256'] for row in manifest['files']}
        receipt_path = source(parent/'evidence/measure1/report.json')
        assert sha(receipt_path) == expected[receipt_path.relative_to(parent).as_posix()]
        receipt = load(receipt_path)
        r['protected_before'] = receipt['protected_before']
        assert all(sha(repo/name) == h for name, h in r['protected_before'].items())
        for case in receipt['cases']:
            label = case['label']
            path = source(parent/'evidence/measure1'/label/'measurement.npz')
            assert sha(path) == expected[path.relative_to(parent).as_posix()] == case['data_sha256']
            with np.load(path) as f:
                audio, chunks = f['native'].copy(), f['C_chunks'].copy()
            positions_path = source(Path(case['original_folder'])/'coordinates.npz')
            assert sha(positions_path) == receipt['inputs'][str(positions_path)]
            positions = np.load(positions_path)['source_seconds']
            phase = inverse_phase(positions, case['native_registered_start_seconds'], case['native_first_frame'], len(audio))
            projector = Projector(phase)
            original, _, _ = execute(label+'_source', audio, phase, projector, dict(source_seconds=positions))
            del projector
            phase_c = np.arange(len(audio))*case['root_hz']/48000
            projector = Projector(phase_c)
            joined = chunks.transpose(1, 0, 2).reshape(len(audio), 18)
            c, _, _ = execute(label+'_C', joined, phase_c, projector)
            del projector
            r['cases'].append(dict(label=label, source=original, generated=c,
                                   coordinate_input=str(positions_path),
                                   native_start_seconds=case['native_registered_start_seconds'],
                                   native_first_frame=case['native_first_frame'], root_hz=case['root_hz']))
            save(a.out/'report.json', r)
            print('PASS six local source/C projections', label, flush=True)
        assert len(r['cases']) == 6
        assert all(sha(repo/name) == h for name, h in r['protected_before'].items())
        r.update(result='native_harmonic_remainder_cross_budgets_measured',
                 known_cases=len(r['known']), real_stereo_inputs=60,
                 C_and_voices_F2_exact=True, source_physical_separation=False,
                 new_runtime_fit=False, audio_candidate=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc))
        raise
    finally:
        save(a.out/'report.json', r)


if __name__ == '__main__':
    main()
