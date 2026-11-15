"""Independently audit a real full288 native render and all reported metrics."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from native_clock_case_audit_v1.identity import verify as identities
    from native_clock_case_audit_v1.clock import verify as clock, integer_model
    from native_clock_case_audit_v1.sound import verify as sound, comparisons, extent
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out / 'executed_audit.py')
    for path in (repo / 'tools/native_clock_case_audit_v1').glob('*.py'):
        dest = a.out / 'executed_modules' / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    r = dict(result='running', inputs={}, maximum_errors={}, renders=[], comparisons={})

    def check(name, left, right, scale, gate):
        left, right = np.asarray(left), np.asarray(right)
        assert left.shape == right.shape, (name, left.shape, right.shape)
        assert np.isfinite(left).all() and np.isfinite(right).all(), name
        if scale == 0:
            assert np.count_nonzero(left) == np.count_nonzero(right) == 0, name
            error = 0.
        else:
            error = float(np.max(abs(left - right)) / scale) if left.size else 0.
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        assert error <= gate, (name, error, gate)

    try:
        source = load(a.study / 'report.json')
        assert source['result'] == 'actual_native_clock_case_measured'
        r['inputs'][str(a.study / 'report.json')] = sha(a.study / 'report.json')
        plan = load(a.study / 'exact_sources/research/native_clock_case_v1_plan.json')
        gates = plan['gates']
        assert source['gates'] == gates
        z, native = identities(source, a.study, repo, r['inputs'])
        probes, integer = integer_model(z, check, gates['scalar_basis_relative_coefficient_L1_max'])
        results = {}
        assert [v['up'] for v in source['renders']] == [16, 32]
        for row in source['renders']:
            file = a.study / row['file']
            assert sha(file) == row['sha256']
            r['inputs'][str(file)] = sha(file)
            with np.load(file) as f:
                arrays = {key: f[key] for key in f.files}
            verified = clock(z, native, arrays, row['up'], check, gates)
            path = a.out / ('independent' + str(row['up']) + '.npz')
            np.savez_compressed(path, **{k: v for k, v in verified.items() if isinstance(v, np.ndarray)},
                                integer_probes=probes, integer_wave=integer)
            r['renders'].append({**{k: v for k, v in verified.items() if not isinstance(v, np.ndarray)},
                                  'file': path.name, 'sha256': sha(path)})
            results['fitted' + str(row['up'])] = arrays['native']
            print('ACTUAL_NATIVE_AUDIT_RENDER', source['label'], row['up'], flush=True)
        sound_file = a.study / source['sound']['file']
        assert sha(sound_file) == source['sound']['sha256']
        r['inputs'][str(sound_file)] = sha(sound_file)
        with np.load(sound_file) as f:
            observed = {key: f[key] for key in f.files}
        results.update(raw=native['raw_native_target'], FIR_only=native['source_FIR_only_target'])
        for name, audio in results.items():
            assert np.array_equal(observed[name + '_audio'], audio)
            windows = sound(name, audio, observed, check, gates)
            for field, value in source['sound']['precision'][name]['broad'].items():
                assert np.array_equal(np.asarray(value), observed[name + '_broad_' + field])
        expected_pairs = {'fitted16_vs_raw', 'fitted32_vs_raw', 'fitted16_vs_FIR_only',
                          'fitted32_vs_FIR_only', 'fitted16_vs_fitted32', 'FIR_only_vs_raw'}
        assert set(source['comparisons']) == expected_pairs
        for label, comparison in source['comparisons'].items():
            left, right = label.split('_vs_')
            r['comparisons'][label] = comparisons(left, right, observed, comparison, check, gates)
        convergence = r['comparisons']['fitted16_vs_fitted32']
        passed = bool(convergence['wave_NRMSE'] is not None
            and convergence['wave_NRMSE'] <= gates['native16_vs_32_wave_NRMSE_max']
            and all(v is not None and v <= gates['native16_vs_32_each_band_complex_NRMSE_max']
                    for v in convergence['band_complex_NRMSE']))
        assert source['native16_32_convergence_passed'] == passed
        eligible = bool(passed and source['source_solver_qualified'] and source['source_fidelity_qualified'])
        assert source['eligible_for_later_source_statistics'] == eligible
        for flag in ('no_gain_matching_or_time_alignment', 'all_original288_orders_and_nodes',
                     'fitted_trajectories_are_diagnostics_never_loops',
                     'source_FIR_only_is_not_complete_upstream_interpolator_inverse',
                     'no_C_or_default_or_hearing_or_sustained_source_promotion'):
            assert source[flag]
        r.update(result='independent_actual_native_clock_case_verified', label=source['label'],
            verification_passed=True, native16_32_convergence_passed=passed,
            source_solver_qualified=source['source_solver_qualified'],
            source_fidelity_qualified=source['source_fidelity_qualified'],
            eligible_for_later_source_statistics=eligible, physical_rate=48000,
            native_frames=len(native['raw_native_target']), windows=windows,
            linear_operator_and_frozen_statistics_verified=True,
            legacy_cross_FFT_normalized_statistics_all_qualified=False,
            sensitivity_is_certified_bound=False, no_producer_or_meter_imports=True,
            producer_sha256=sha(a.study / 'report.json'), auditor_sha256=sha(__file__),
            no_sustained_source_or_C_or_hearing_qualification=True)
        save(a.out / 'report.json', r)
        print('ACTUAL_NATIVE_AUDIT_COMPLETE', source['label'], 'verified; convergence', passed,
              'eligible', eligible, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
