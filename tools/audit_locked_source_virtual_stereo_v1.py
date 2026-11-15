"""Extend prior case checks with direct CSD/M-S and frozen joint statistics."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'prior-audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_diagnostics_v1.audit_stereo import verify
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], sources={}, inputs={}, maximum_errors={})

    def read(path):
        path = Path(path); report['inputs'][str(path)] = sha(path)
        return load(path)

    def check(name, actual, expected, scale):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all()
        if scale == 0:
            assert np.count_nonzero(actual) == np.count_nonzero(expected) == 0
            error = 0.
        else: error = float(np.max(abs(actual-expected))/scale) if actual.size else 0.
        report['maximum_errors'][name] = max(error, report['maximum_errors'].get(name, 0.))
        assert error < 2e-11, (name, error)

    try:
        names = {'tools/audit_locked_source_virtual_stereo_v1.py',
            'tools/locked_source_diagnostics_v1/audit_stereo.py', 'tools/native_clock_case_audit_v1/sound.py',
            'research/locked_source_diagnostics_v1_plan.json', 'tools/research_archive_v1.py'}
        for name in sorted(names):
            dest = args.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); report['sources'][name] = sha(dest)
        source, prior = read(args.study/'report.json'), read(args.prior_audit/'report.json')
        assert prior['result'] == 'independent_locked_source_virtual_verified' and prior['all_consumer_checks_passed']
        assert prior['producer_sha256'] == sha(args.study/'report.json')
        assert [row['label'] for row in source['cases']] == [row['label'] for row in prior['cases']]
        for case in source['cases']:
            path = args.study/case['report']; assert sha(path) == case['sha256']
            info = read(path)
            assert info['result'] == 'locked_source_virtual_case_measured'
            capture = next(Path(name) for name in info['inputs'] if Path(name).name == 'capture.npz')
            for name, wanted in info['inputs'].items():
                assert sha(name) == wanted; report['inputs'][name] = wanted
            with np.load(capture) as saved: orders = saved['orders']
            assert not info['meter_protocol']['legacy_cross_operator_all_statistics_qualified']
            assert info['meter_protocol']['retained_legacy_normalized_failure_count'] == 5
            observations = []
            for region in info['regions']:
                output = path.parent/region['file']; assert sha(output) == region['sha256']
                report['inputs'][str(output)] = sha(output)
                with np.load(output) as saved: arrays = {name: saved[name] for name in saved.files}
                for label in ('reference', 'candidate'):
                    observation = verify(label, arrays[label+'_audio'], arrays, orders, check)
                    observations.append(dict(region=region['region'], audio=label, **observation))
            report['cases'].append(dict(label=case['label'], all_stereo_checks_passed=True, observations=observations))
            save(args.out/'report.json', report)
            print('LOCKED_VIRTUAL_STEREO', case['label'], 'PASS', flush=True)
        report.update(result='independent_locked_source_virtual_stereo_verified', all_stereo_checks_passed=True,
            producer_sha256=sha(args.study/'report.json'), prior_audit_sha256=sha(args.prior_audit/'report.json'),
            actual_recorded_diagnostics_verified=source['result'] == 'locked_source_real_virtual_measured',
            physical_source_separation_or_native_or_hearing_qualified=False)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
