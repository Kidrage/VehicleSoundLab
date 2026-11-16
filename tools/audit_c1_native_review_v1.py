"""Independently verify saved native-loss bins, all table fields and CSV publication."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_native_review_v1.audit import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), sources={})
    errors = {}
    def check(name, actual, expected, scale):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, name
        error = float(np.max(abs(actual-expected)))/max(float(scale), 1e-300)
        errors[name] = error
        if not np.isfinite(error) or error > 2e-11: raise ValueError((name, error))
    try:
        for name in ('tools/audit_c1_native_review_v1.py', 'tools/c1_native_review_v1/audit.py',
            'tools/research_archive_v1.py'):
            path = a.out/'exact_sources'/name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path); r['sources'][name] = sha(path)
        producer = load(a.study/'report.json')
        assert producer['verification_passed'] and producer['result'] == 'c1_native_loss_review_measured_and_independently_verified'
        for name, digest in producer['sources'].items(): assert sha(repo/name) == digest
        for name, digest in producer['inputs'].items(): assert sha(name) == digest
        for name, digest in producer['files'].items(): assert sha(a.study/name) == digest
        with np.load(a.study/'measured.npz') as packet: data = {k:packet[k] for k in packet.files}
        rows = load(a.study/'bands.json'); assert rows == producer['bands']
        r['verification'] = verify(data, rows, check)
        # Exact text round-trip checks for EVERY numeric CSV value, separately
        # from the total-source-scale spectral comparisons.
        with (a.study/'bands.csv').open(encoding='utf-8', newline='') as stream:
            csv_rows = list(csv.reader(stream))
        assert len(csv_rows) == len(rows)+1 and len(csv_rows[0]) == 14
        numeric_cells = 0
        for csv_row, row in zip(csv_rows[1:], rows):
            auto, cross = row['component_auto_FS2_LR'], row['component_signed_cross_FS2_LR']
            expected = [sum(row[k]) for k in ('reference_FS2_LR', 'candidate_FS2_LR', 'error_FS2_LR')]
            expected += [row['combined_complex_NRMSE'], row['fraction_of_total_observed_error'],
                sum(row['radial_error_FS2_LR']), sum(row['angular_error_FS2_LR'])]
            expected += [sum(v) for v in auto]+[sum(cross[i][j]) for i,j in ((0,1),(0,2),(1,2))]
            assert csv_row[0] == str(row['low_Hz'])+'-'+str(min(row['high_exclusive_Hz'], 24000))
            # CSV has one label plus 13 numeric fields.
            assert len(csv_row) == 14
            for actual, value in zip(csv_row[1:], expected):
                assert float(actual) == value
                numeric_cells += 1
        check('published_total_reference', producer['observed_total_reference_FS2'],
            math.fsum(data['raw_bin_power'].ravel()), max(producer['observed_total_reference_FS2'], 1e-300))
        check('published_total_error', producer['observed_total_error_FS2'],
            math.fsum(data['bin_error_power'].ravel()), max(producer['observed_total_error_FS2'], 1e-300))
        order = np.argsort(data['bin_error_power'].sum(axis=1))[::-1][:20]
        expected_bins = [dict(Hz=float(data['frequency'][k]),
            error_FS2=float(data['bin_error_power'][k].sum())) for k in order]
        assert producer['maximum_error_bins'] == expected_bins
        import xml.etree.ElementTree as ET
        for name in ('native_loss.svg', 'native_error_geometry.svg'): ET.parse(a.study/name)
        r.update(result='independent_c1_native_review_verified', verification_passed=True,
            numeric_CSV_cells_bitwise_checked=numeric_cells, all_published_band_fields_checked=True,
            maximum_errors=errors, maximum_comparison_error=max(errors.values()),
            independent_linear_spectra_and_frozen_series_ratios_separate=True,
            no_crossFFT_ratio_bound_acoustic_or_runtime_qualification=True)
        save(a.out/'report.json', r)
        print('C1_NATIVE_REVIEW_AUDIT', r['result'], numeric_cells, max(errors.values()), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error), maximum_errors=errors)
        save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
