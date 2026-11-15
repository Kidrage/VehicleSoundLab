"""Independently verify published actual native numeric rows and source hashes."""
import argparse
import math
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
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out / 'executed_audit.py')
    r = dict(result='running', cases=[], inputs={})
    try:
        source = load(a.study / 'report.json')
        assert source['result'] == 'actual_native_cases_publication_prepared'
        r['inputs'][str(a.study / 'report.json')] = sha(a.study / 'report.json')
        for name, digest in source['sources'].items():
            assert sha(a.study / 'exact_sources' / name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for c in source['cases']:
            path = a.study / c['file']; assert sha(path) == c['sha256']
            assert sha(a.study / c['figure']) == c['figure_sha256']
            assert sha(a.study / c['vector']) == c['vector_sha256']
            if 'focus_figure' in c:
                assert sha(a.study / c['focus_figure']) == c['focus_figure_sha256']
                assert sha(a.study / c['focus_vector']) == c['focus_vector_sha256']
            row = load(path)
            native, audit = load(row['native_report']), load(row['native_audit'])
            assert audit['verification_passed'] and audit['producer_sha256'] == sha(row['native_report'])
            for field in ('source_solver_qualified', 'source_fidelity_qualified',
                          'native16_32_convergence_passed', 'eligible_for_later_source_statistics'):
                assert row[field] == native[field] == audit[field]
            assert row['original_weighted_errors'] == native['source']['existing_weighted_metrics']
            assert row['comparisons'] == native['comparisons']
            with np.load(row['sound_file']) as f:
                for name, signal in row['signals'].items():
                    for field, key in (('mean_power_FS2', 'mean_power'), ('mean_mid_side_FS2', 'mean_mid_side'), ('CV', 'CV')):
                        assert np.array_equal(signal[field], f[name + '_broad_' + key])
                    coherence = f[name + '_broad_complex_coherence']
                    assert np.array_equal(signal['complex_coherence'], np.column_stack((coherence.real, coherence.imag)))
                    for ratio, (m, s) in zip(signal['side_over_mid_dB'], f[name + '_broad_mean_mid_side']):
                        if m == 0 or s == 0:
                            assert ratio is None
                        else:
                            expected = 10 * math.log10(float(s) / float(m))
                            assert abs(ratio - expected) <= 2e-11
                    assert signal['precision'] == native['sound']['precision'][name]['broad']
            r['cases'].append(dict(label=row['label'], all_publication_fields_verified=True,
                eligible_for_later_source_statistics=row['eligible_for_later_source_statistics']))
        r.update(result='independent_actual_native_publication_verified', all_publication_fields_verified=True,
                 producer_sha256=sha(a.study / 'report.json'), auditor_sha256=sha(__file__),
                 no_hearing_or_source_separation_or_sustained_or_C_qualification=True)
        save(a.out / 'report.json', r)
        print('ACTUAL_NATIVE_PUBLICATION_AUDIT', len(r['cases']), 'PASS', flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r); raise


if __name__ == '__main__':
    main()
