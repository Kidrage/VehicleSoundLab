"""Independent complete published-table/data check, without publisher imports."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_tail_v1.audit_measure import masks, LABELS
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', checks={}, inputs={})
    try:
        info = load(a.study/'report.json')
        assert info['result'] == 'locked_source_tail_review_published'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items():
            assert sha(name) == expected
        shutil.copytree(a.study/'exact_sources', a.out/'exact_sources')
        root = Path(info['study'])
        stages, captures = {}, {}
        for mode, stage, audit_stage in (('known', 'known1', 'known_audit1'), ('real', 'real1', 'audit1')):
            stages[mode] = load(root/stage/'report.json')
            audit = load(root/audit_stage/'report.json')
            assert audit['verification_passed'] and audit['producer_sha256'] == sha(root/stage/'report.json')
            with np.load(root/stage/'capture.npz') as f:
                captures[mode] = {key: f[key] for key in f.files}
            assert info['full_observations'][mode] == stages[mode]['observations']
        def check(name, got, expected):
            assert np.isfinite(got) and np.isfinite(expected)
            error = abs(got-expected)/max(abs(got), abs(expected)) if got or expected else 0.
            assert error < 2e-11, (name, got, expected, error)
            r['checks'][name] = error
        frequency = np.arange(2049)*16
        band_masks = dict(zip(LABELS, masks()))
        def power(mode, name, band):
            return float(captures[mode][name+'_Welch_FS2'][band_masks[band]].sum())
        original = stages['real']['original_metrics']['target_supported_band_complex_NRMSE'][-1]
        check('original_highest', info['original_virtual_highest_NRMSE'], original)
        assert original > .02 == info['original_gate_unchanged']
        assert not info['source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
        for key, name in (('original128_Welch_FS2', 'nominal128'), ('reference2048_Welch_FS2', 'reference2048')):
            check(key, info['real_above_centre'][key], power('real', name, 'above18432'))
        check('real_tail_ratio', info['real_above_centre']['reference2048_to_original128_power_ratio'],
              power('real', 'reference2048', 'above18432')/power('real', 'nominal128', 'above18432'))
        for key, name in (('registered_above_centre_Welch_FS2', 'exact_registered'), ('affine_above_centre_Welch_FS2', 'exact_affine')):
            check(key, info['known_clock'][key], power('known', name, 'above18432'))
        check('known_clock_ratio', info['known_clock']['registered_to_affine_above_power_ratio'],
              power('known', 'exact_registered', 'above18432')/power('known', 'exact_affine', 'above18432'))
        k = captures['known']; delta = k['signal__nominal128']-k['signal__ideal_native_nominal128']
        check('FIR_max', info['known_FIR_numerical_sensitivity']['max_FS'], float(np.max(abs(delta))))
        check('FIR_NRMSE', info['known_FIR_numerical_sensitivity']['NRMSE'], float(np.linalg.norm(delta)/np.linalg.norm(k['signal__exact_registered'])))
        assert sha(a.study/'all_bands.csv') == info['table_sha256']
        with (a.study/'all_bands.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        expected_keys = {(mode, name, band) for mode, stage in stages.items()
            for name in stage['observations']['signals'] for band in LABELS}
        actual_keys = [(row['mode'], row['signal'], row['band']) for row in rows]
        assert set(actual_keys) == expected_keys and len(actual_keys) == len(expected_keys) == info['table_rows']
        for row in rows:
            mode, name, band = row['mode'], row['signal'], row['band']
            prefix = mode+'_'+name+'_'+band
            mask = band_masks[band]; capture = captures[mode]
            for suffix, array in (('weighted_mass', name+'_weighted_mass'), ('Welch_FS2', name+'_Welch_FS2')):
                for c, channel in enumerate(('L', 'R')):
                    check(prefix+'_'+suffix+channel, float(row[suffix+'_'+channel]), float(capture[array][mask, c].sum()))
            G = capture[name+'_vs_reference_'+band+'_Gram']
            den = G[0, 0].real+G[1, 1].real
            expected = np.sqrt((G[2, 2].real+G[3, 3].real)/den) if den else None
            if expected is None:
                assert row['transform_difference_NRMSE'] == ''
            else:
                check(prefix+'_transformNRMSE', float(row['transform_difference_NRMSE']), float(expected))
                check(prefix+'_timeNRMSE', float(row['time_difference_NRMSE']),
                      float(np.sqrt(capture[name+'_time_difference_weighted_mass'][mask].sum()/den)))
            for c, channel in enumerate(('L', 'R')):
                check(prefix+'_cross'+channel, float(row['signed_cross_'+channel]), float(2*G[c, c+2].real))
        assert sha(a.study/'plot_data.npz') == info['plot_data_sha256']
        with np.load(a.study/'plot_data.npz') as f:
            assert np.array_equal(f['virtual_frequency'], frequency)
            for mode, capture in captures.items():
                for key, array in capture.items():
                    if key.endswith(('_Welch_FS2', '_weighted_mass')):
                        assert np.array_equal(f[mode+'__'+key], array)
        assert len(info['figures']) == 4
        for name, expected in info['figures'].items():
            assert sha(a.study/name) == expected
        r.update(result='independent_locked_source_tail_review_verified', verification_passed=True,
            producer_sha256=sha(a.study/'report.json'), all160_rows_and_plot_arrays_verified=True,
            table_rows=len(rows), source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
            no_new_source_or_hearing_qualification=True)
        save(a.out/'report.json', r)
        print('INDEPENDENT_TAIL_REVIEW_COMPLETE', len(rows), len(r['checks']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
