"""Complete native audit with explicit FP64 centering; retain old failures."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_native_diagnostics_v1.audit_case import verify
    from c1_native_diagnostics_v1.declared_statistics import statistics
    from extraction_sound_v1.measure import statistics as produced_statistics
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', schema='vsl.c1-native-declared-centering-audit/1',
        producer_sha256=sha(a.study/'report.json'), sources={}, inputs={}, controls=[], cases=[], maximum_errors={})

    def check(name, got, expected, scale, gate):
        got, expected = np.asarray(got), np.asarray(expected)
        assert got.shape == expected.shape and np.isfinite(got).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(got-expected))) if got.size else 0.
        relative = error/max(float(scale), 1e-300)
        if not scale:
            assert error == 0, name
        assert relative <= gate, (name, relative, gate)
        r['maximum_errors'][name] = max(relative, r['maximum_errors'].get(name, 0.))

    try:
        info = load(a.study/'report.json')
        assert info['schema'] == 'vsl.c1-declared-native-diagnostic/1'
        assert info['result'] == 'c1_declared_native_'+info['mode']+'_measured'
        for name, digest in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in info['inputs'].items():
            assert sha(name) == digest
        r['inputs'].update(info['inputs'])
        r['inputs'][str(a.study/'report.json')] = r['producer_sha256']
        names = {'tools/audit_c1_native_declared_v1.py',
            'tools/c1_native_diagnostics_v1/declared_statistics.py', 'tools/c1_native_diagnostics_v1/audit_case.py'}
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        # Manufactured finite series before saved source observations. The
        # cancellation fixture makes the rounding convention observable.
        for label in ('varying', 'constant', 'zero', 'silent_right', 'rounded_mean'):
            power = (np.arange(3*12).reshape(3, 6, 2)%11+1).astype(float)/16
            if label == 'constant':
                power[:] = power[0]
            elif label == 'zero':
                power[:] = 0
            elif label == 'silent_right':
                power[:, :, 1] = 0
            elif label == 'rounded_mean':
                power[:] = np.array([1e16, 1., 1.])[:, None, None]
            cross = .4*np.sqrt(power[:, :, 0]*power[:, :, 1])*(1+.2j)
            ms = np.stack(((power.sum(axis=2)+2*cross.real)/4,
                           (power.sum(axis=2)-2*cross.real)/4), axis=2)
            oracle, actual = statistics(power, cross, ms), produced_statistics(power, cross, ms)
            for field, expected in oracle.items():
                if expected.dtype == bool:
                    assert np.array_equal(actual[field], expected)
                else:
                    scale = float(np.max(abs(expected))) if expected.size else 0.
                    check('known_'+label+'_'+field, actual[field], expected, scale, 2e-11)
            if label == 'rounded_mean':
                assert np.all(oracle['mean_power'] == np.float64(1e16)/3)
                assert np.all(oracle['mean_power'] != (np.longdouble(1e16)+2)/3)
            r['controls'].append(dict(label=label, all_fields_verified=True))
        for row in info['cases']:
            root = a.study/row['label']
            for name, digest in row['files'].items():
                assert sha(root/name) == digest
                r['inputs'][str(root/name)] = digest
            r['cases'].append(verify(root, row, info['mode'], info['gates'], check))
            save(a.out/'report.json', r)
            print('C1_NATIVE_DECLARED_AUDIT', row['label'], flush=True)
        failures = [dict(label=case['label'], **failure) for case in r['cases']
            for observer in case['native_observations'].values()
            for failure in observer['retained_original_failures']]
        r.update(result='independent_c1_declared_native_centering_'+info['mode']+'_verified', verification_passed=True,
            all_known_qualified=all(c['known_wave_qualified'] for c in r['cases']) if info['mode'] == 'known' else None,
            all_operator_and_declared_statistics_verified=True,
            original_fsum_centered_comparisons_all_passed=not failures,
            retained_original_fsum_centering_failures=failures,
            original_gates_unchanged=True, original_failed_audit_not_relabelled=True,
            eligible_for_later_source_statistics=False, no_runtime_or_naturalness_or_hearing_promotion=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
