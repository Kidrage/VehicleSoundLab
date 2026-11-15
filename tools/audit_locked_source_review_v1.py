"""Independently check published physical/stereo numbers and retained failures.

This checks publication of an already independently verified signal analysis;
it does not repeat a source fit, promote a fidelity flag or certify FFT error.
"""
import argparse
import csv
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
    os.environ['OPENBLAS_NUM_THREADS'] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out / 'executed_audit.py')
    r = dict(result='running', inputs={}, checked_values=0, maximum_absolute_error=0.)

    def check(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        assert x.shape == y.shape and np.isfinite(x).all() and np.isfinite(y).all()
        error = float(np.max(abs(x-y))) if x.size else 0.
        assert error < 2e-12, error
        r['maximum_absolute_error'] = max(r['maximum_absolute_error'], error)
        r['checked_values'] += int(x.size)

    try:
        source = load(a.study / 'report.json')
        assert source['result'] == 'locked_source_terminal_diagnostics_reviewed'
        r['inputs'][str(a.study / 'report.json')] = sha(a.study / 'report.json')
        for name, expected in source['inputs'].items():
            assert sha(name) == expected
            r['inputs'][name] = expected
        for name, expected in source['sources'].items():
            assert sha(a.study / 'exact_sources' / name) == expected
        native_path = next(Path(name) for name in source['inputs'] if Path(name).parent.name == 'native_real1' and Path(name).name == 'report.json')
        native = load(native_path)
        audit_path = next(Path(name) for name in source['inputs'] if Path(name).parent.name == 'native_real_audit1')
        audit = load(audit_path)
        assert audit['result'] == 'independent_locked_source_native_verified' and audit['verification_passed']
        assert audit['producer_sha256'] == sha(native_path)
        assert native['label'] == source['label'] and native['sound']['frames'] == source['native_frames']
        for key, value in source['flags'].items():
            assert value == native[key] == audit[key]
        assert not source['flags']['source_fidelity_qualified'] and not source['flags']['eligible_for_later_source_statistics']
        with np.load(native_path.parent / native['sound']['file']) as z:
            for name, s in source['signals'].items():
                for field, key in (('mean_power_FS2', 'mean_power'), ('mean_mid_side_FS2', 'mean_mid_side'), ('CV', 'CV')):
                    check(s[field], z[name + '_broad_' + key])
                ms = z[name + '_broad_mean_mid_side']
                check(s['side_over_mid_dB'], [10*np.log10(row[1]/row[0]) for row in ms])
                check(s['complex_coherence'], [[v.real, v.imag] for v in z[name + '_broad_complex_coherence']])
        assert set(source['comparisons']) == set(native['comparisons'])
        for name, c in source['comparisons'].items():
            original = native['comparisons'][name]
            s = original['signed_changes']['broad']
            for key in ('wave_NRMSE', 'channel_wave_NRMSE', 'band_complex_NRMSE'):
                check(c[key], original[key])
            for key in ('power_change_dB', 'complex_coherence_change', 'CV_change',
                        'covariance_relative_difference', 'lag_covariance_relative_difference'):
                check(c[key], s[key])
            left, right = name.split('_vs_')
            direct_side = np.asarray(source['signals'][left]['side_over_mid_dB']) - np.asarray(source['signals'][right]['side_over_mid_dB'])
            check(c['side_over_mid_change_dB'], direct_side)
            check(c['main_0_14k_max_side_over_mid_change_dB'], max(abs(direct_side[:5])))
            check(c['main_0_14k_max_power_change_dB'], max(abs(v) for row in s['power_change_dB'][:5] for v in row))
            check(c['main_0_14k_max_complex_coherence_change'], max(abs(complex(*row)) for row in s['complex_coherence_change'][:5]))
            check(c['main_0_14k_max_CV_change'], max(abs(v) for row in s['CV_change'][:5] for v in row))
        table = a.study / source['table']['file']
        assert sha(table) == source['table']['sha256']
        rows = list(csv.DictReader(table.open(encoding='utf-8-sig', newline='')))
        assert len(rows) == 24
        for row in rows:
            b = ['0-3', '3-6', '6-8', '8-10', '10-14', '14-24'].index(row['physical_band_kHz'])
            s = source['signals'][row['source']]
            check([float(row[k]) for k in ('L_FS2', 'R_FS2', 'Mid_FS2', 'Side_FS2', 'Side_over_Mid_dB',
                'coherence_real', 'coherence_imag', 'CV_L', 'CV_R')],
                [*s['mean_power_FS2'][b], *s['mean_mid_side_FS2'][b], s['side_over_mid_dB'][b],
                 *s['complex_coherence'][b], *s['CV'][b]])
        for row in source['figures']:
            assert sha(a.study / row['file']) == row['sha256']
        assert len(source['figures']) == 4 and source['all_six_physical_bands_retained']
        failed = [load(name) for name in source['inputs'] if Path(name).parent.name in ('real1', source['label'] + '_audit')
                  and Path(name).name == 'report.json']
        # Includes the separate successful math proof; preserve both actual failures.
        assert sum(v.get('result') == 'failed' for v in failed) == 2
        assert source['original_terminal_and_cross_operator_failures_retained']
        r.update(result='independent_locked_source_review_verified', verification_passed=True,
            figures_require_separate_visual_inspection=True, no_fidelity_or_sustained_or_C_or_hearing_promotion=True)
        save(a.out / 'report.json', r)
        print('LOCKED_SOURCE_REVIEW_AUDIT', r['checked_values'], r['maximum_absolute_error'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
