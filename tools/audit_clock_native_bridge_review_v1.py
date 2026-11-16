"""Independently bind all native-bridge publication cells to audited evidence."""
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
        review = load(a.review/'report.json'); assert review['result'] == 'clock_native_bridge_review_published'
        for name, expected in review['inputs'].items():
            assert sha(name) == expected; r['inputs'][name] = expected
        for name, expected in review['sources'].items(): assert sha(a.review/'exact_sources'/name) == expected
        study, audit = Path(review['study']), Path(review['audit'])
        info, proof = load(study/'report.json'), load(audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(study/'report.json')
        with np.load(study/'sound.npz') as z: d = {k:z[k] for k in z.files}
        count = 0; table_rows = {}
        def rows(name):
            assert sha(a.review/name) == review['tables'][name]
            with (a.review/name).open(encoding='utf-8', newline='') as f: result = list(csv.reader(f))[1:]
            table_rows[name] = len(result); return result
        def numeric(got, expected):
            nonlocal count
            actual = np.asarray(got, float); wanted = np.asarray(expected)
            assert actual.shape == wanted.shape and np.array_equal(actual, wanted)
            count += actual.size
        comparison_rows = rows('comparisons.csv')
        pending, expected_paths = [('', info['comparisons'])], set()
        while pending:
            path, value = pending.pop()
            if isinstance(value, (dict, list)):
                values = value.items() if isinstance(value, dict) else enumerate(value)
                pending.extend((path+'/'+str(k), child) for k, child in values)
            else: expected_paths.add(path)
        assert len(comparison_rows) == len({row[0] for row in comparison_rows}) == len(expected_paths)
        assert {row[0] for row in comparison_rows} == expected_paths
        for path, text in comparison_rows:
            value = info['comparisons']
            for token in path.split('/')[1:]: value = value[int(token)] if isinstance(value, list) else value[token]
            assert text == '' if value is None else float(text) == value
            count += value is not None
        assert table_rows['comparisons.csv'] == review['signed_comparison_leaves']
        band_rows = rows('bands.csv')
        expected_names = ('raw', 'FIR_only', 'C1_16', 'C1_32', 'PL_16', 'PL_32')
        expected_bands = ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k')
        assert {(row[0], row[1]) for row in band_rows} == {(n,b) for n in expected_names for b in expected_bands}
        for row in band_rows:
            name, label = row[:2]; i = ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-24k').index(label)
            coh = d[name+'_broad_complex_coherence'][i]
            numeric(row[2:], np.r_[d[name+'_broad_mean_power'][i], d[name+'_broad_mean_mid_side'][i],
                d[name+'_broad_CV'][i], coh.real, coh.imag])
        assert table_rows['bands.csv'] == 36
        upper_rows = rows('upper_bands.csv')
        assert {(row[0], row[1]) for row in upper_rows} == {(n,b) for n in expected_names for b in ('14-16k', '16-20k', '20-22k', '22-24k')}
        for row in upper_rows:
            name, label = row[:2]; i = ('14-16k', '16-20k', '20-22k', '22-24k').index(label)
            cross = d[name+'_upper_cross'][:, i].mean()
            numeric(row[2:], np.r_[d[name+'_upper_power'][:, i].mean(axis=0),
                d[name+'_upper_mid_side'][:, i].mean(axis=0), cross.real, cross.imag])
        assert table_rows['upper_bands.csv'] == 24
        expected = [np.arange(2049)*48000/4096]
        for name in ('raw', 'FIR_only', 'C1_16', 'C1_32', 'PL_16', 'PL_32'):
            p = d[name+'_bin_power'].mean(axis=0); c = d[name+'_bin_cross'].mean(axis=0); m = d[name+'_bin_mid_side'].mean(axis=0)
            expected.extend((p[:, 0], p[:, 1], c.real, c.imag, m[:, 0], m[:, 1]))
        numeric(rows('spectra.csv'), np.column_stack(expected))
        for name, expected_hash in review['figures'].items(): assert sha(a.review/name) == expected_hash
        r.update(result='independent_clock_native_bridge_review_verified', verification_passed=True,
            all_published_numbers_bitwise_roundtrip=True, verified_numeric_values=int(count), table_rows=table_rows,
            figures_require_separate_visual_inspection=True)
        save(a.out/'report.json', r); print('BRIDGE_REVIEW_INDEPENDENT', count, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
