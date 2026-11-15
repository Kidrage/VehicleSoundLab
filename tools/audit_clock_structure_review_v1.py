"""Independent all-row publication binding and numerical check."""
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
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', numeric_values_checked=0, maximum_relative_error=0.)
    try:
        info = load(a.study/'report.json'); assert info['result'] == 'clock_structure_review_published'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items():
            assert sha(name) == expected
        shutil.copytree(a.study/'exact_sources', a.out/'exact_sources')
        root = Path(info['study']); sources, arrays = {}, {}
        for mode, stage, audit in (('known', 'known1', 'known_audit1'), ('real', 'real1', 'audit1')):
            sources[mode] = load(root/stage/'report.json'); proof = load(root/audit/'report.json')
            assert proof['verification_passed'] and proof['producer_sha256'] == sha(root/stage/'report.json')
            with np.load(root/stage/'capture.npz') as f:
                arrays[mode] = {key: f[key] for key in f.files}
        assert info['geometry'] == sources['real']['geometry']
        assert info['known'] == sources['known']['known']
        assert info['known_observations'] == sources['known']['observations']
        real, known = arrays['real'], arrays['known']
        def check(got, expected):
            got, expected = float(got), float(expected)
            assert np.isfinite([got, expected]).all()
            error = abs(got-expected)/max(abs(got), abs(expected)) if got or expected else 0.
            assert error < 2e-12, (got, expected, error)
            r['numeric_values_checked'] += 1
            r['maximum_relative_error'] = max(r['maximum_relative_error'], error)
        for name, expected in info['tables'].items():
            assert sha(a.study/name) == expected
        with (a.study/'all_nodes.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == info['node_rows'] == len(real['jumps'])
        for i, row in enumerate(rows):
            assert int(row['event_index']) == i and int(row['observed_phase_node']) == int(real['graph_special'][i+1])
            for key, value in (('virtual_sample', real['jump_node'][i]), ('source_seconds', real['graph_y'][i+1]),
                               ('left_seconds_per_sample', real['slopes'][i]), ('right_seconds_per_sample', real['slopes'][i+1]),
                               ('jump_seconds_per_sample', real['jumps'][i])):
                check(row[key], value)
        with (a.study/'all_curvature.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == info['curvature_rows'] == len(real['actual_d2'])
        for i, row in enumerate(rows):
            check(row['virtual_sample'], real['query'][i+1]); check(row['actual_d2_seconds'], real['actual_d2'][i])
            for c, name in enumerate(('observed_phase_nodes', 'other_coarse_nodes', 'preservation_join', 'floating_remainder')):
                check(row[name], real['components'][c, i])
            assert int(row['observed_support']) == int(real['special_support'][i])
        mask = np.arange(2049)*16 > 18432
        powers = {}
        for name in sources['known']['observations']['signals']:
            values = known[name+'_Welch_FS2'][mask].sum(axis=0)
            powers[name] = float(values.sum())
            for c in (0, 1):
                check(info['controlled_above_centre']['signals'][name]['Welch_FS2_LR'][c], values[c])
                check(info['controlled_above_centre']['signals'][name]['weighted_mass_LR'][c],
                      known[name+'_weighted_mass'][mask, c].sum())
        check(info['controlled_above_centre']['C0_to_exact_smooth_power_ratio'], powers['manufactured_C0']/powers['exact_smooth'])
        check(info['controlled_above_centre']['sampled_to_exact_smooth_power_ratio'], powers['sampled_smooth_PL']/powers['exact_smooth'])
        assert sha(a.study/'plot_data.npz') == info['plot_data_sha256']
        with np.load(a.study/'plot_data.npz') as f:
            for key in ('query', 'actual', 'actual_d2', 'components', 'special_support', 'jump_node', 'jumps', 'graph_special', 'Gram'):
                assert np.array_equal(f[key], real[key])
            assert np.array_equal(f['virtual_frequency'], np.arange(2049)*16)
            for name in powers:
                assert np.array_equal(f[name+'_Welch_FS2'], known[name+'_Welch_FS2'])
        assert len(info['figures']) == 4
        for name, expected in info['figures'].items():
            assert sha(a.study/name) == expected
        assert not info['original_source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
        r.update(result='independent_clock_structure_review_verified', verification_passed=True,
            producer_sha256=sha(a.study/'report.json'), all22527_nodes_and18432_curvature_rows_verified=True,
            clock_geometry_not_acoustic_power_or_real_tail_causal_fraction=True,
            no_actual_clock_or_source_promotion=True)
        save(a.out/'report.json', r)
        print('INDEPENDENT_CLOCK_REVIEW_COMPLETE', r['numeric_values_checked'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
