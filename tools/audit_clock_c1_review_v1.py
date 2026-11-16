"""Independently bind every published CSV numeric value to audited evidence."""
import argparse
import csv
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'review', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', inputs={}, producer_sha256=sha(a.review/'report.json'))
    try:
        review = load(a.review/'report.json'); assert review['result'] == 'clock_c1_review_published'
        for name, expected in review['inputs'].items():
            assert sha(name) == expected; r['inputs'][name] = expected
        for name, expected in review['sources'].items():
            assert sha(a.review/'exact_sources'/name) == expected
        study, audit = Path(review['study']), Path(review['audit'])
        report, proof = load(study/'report.json'), load(audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(study/'report.json')
        with np.load(study/'capture.npz') as z:
            d = {k:z[k] for k in z.files}
        expected = dict(
            **{'clock.csv': np.column_stack((d['query'], d['old_positions'], d['positions'], (d['positions']-d['old_positions'])*1e6))},
            **{'intervals.csv': np.column_stack((d['x'][:-1], d['x'][1:], d['y'][:-1], d['y'][1:], d['coefficients'].T, d['interval_minimum_derivative']))},
            **{'spectra.csv': np.column_stack((np.arange(2049)*16, d['original_Welch_FS2'], d['C1_Welch_FS2']))})
        bands = []
        for b in report['stereo']['bands']:
            group = report['observations']['comparisons']['C1']['groups'][b['band']]
            bands.append([*b['old_Welch_FS2_LR'], *b['C1_Welch_FS2_LR'], *b['power_change_dB_LR'], b['coherence_complex_difference'],
                b['old_Side_Mid_dB'], b['C1_Side_Mid_dB'], *b['CV_change_LR'], group['transform_difference_NRMSE'], group['time_difference_NRMSE']])
        expected['bands.csv'] = np.asarray(bands)
        count, table_rows = 0, {}
        for name, numeric in expected.items():
            assert sha(a.review/name) == review['tables'][name]
            with (a.review/name).open(encoding='utf-8', newline='') as f:
                rows = list(csv.reader(f))[1:]
            if name == 'bands.csv':
                assert [row[0] for row in rows] == [b['band'] for b in report['stereo']['bands']]
                rows = [row[1:] for row in rows]
            got = np.asarray(rows, float)
            assert got.shape == numeric.shape and np.array_equal(got, numeric), name
            count += got.size; table_rows[name] = len(rows)
        for name, expected_hash in review['figures'].items():
            assert sha(a.review/name) == expected_hash
        r.update(result='independent_clock_c1_review_verified', verification_passed=True,
            all_numeric_values_bitwise_roundtrip=True, verified_numeric_values=int(count), table_rows=table_rows,
            figures_require_separate_visual_inspection=True)
        save(a.out/'report.json', r); print('C1_REVIEW_INDEPENDENT', count, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
