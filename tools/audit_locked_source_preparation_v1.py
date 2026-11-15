"""Independent five-source transfer, unchanged calibration and complete probes."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from observer_frequency_v1.reduced_oracle import synthesize
    from observer_complete_v1.audit_oracle import full_frame
    from locked_source_fit_v1.oracle import make

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', cases=[], maximum_errors={}, inputs={})

    def check(name, actual, expected):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, (name, actual.shape, expected.shape)
        error = float(np.max(abs(actual-expected))/max(1., float(np.max(abs(expected)))))
        report['maximum_errors'][name] = max(error, report['maximum_errors'].get(name, 0.))
        assert error < 2e-12, (name, error)

    try:
        source = load(args.study/'report.json')
        report['inputs'][str(args.study/'report.json')] = sha(args.study/'report.json')
        expected_labels = ['F3 Fifth First Mid', 'F3 Fifth First Late', 'F3 Fifth Second Early',
                           'F3 Fifth Second Mid', 'F3 Fifth Second Late']
        assert source['result'] == 'locked_source_five_prepared' and source['no_inverse_fit']
        assert source['all_resources_passed'] and source['retained_five_disk_passed']
        assert [row['label'] for row in source['cases']] == expected_labels and source['nominal_sinc_radius'] == 128
        for name, wanted in source['sources'].items():
            assert sha(repo/name) == sha(args.study/'exact_sources'/name) == wanted
        for path, wanted in source['inputs'].items():
            assert sha(path) == wanted; report['inputs'][path] = wanted
        for row in source['cases']:
            path = args.study/row['file']; assert sha(path) == row['sha256']
            report['inputs'][str(path)] = sha(path)
            with np.load(path) as saved: z = {name: saved[name] for name in saved.files}
            with np.load(row['original_preparation']) as saved: old = {name: saved[name] for name in saved.files}
            with np.load(row['source_query_file']) as saved: new = {name: saved[name] for name in saved.files}
            assert np.array_equal(z['audio'], new['sinc128'])
            assert np.array_equal(z['target'], new['sinc128'][2048:-2048])
            assert np.array_equal(z['metric_target'], old['target'])
            for name in old:
                if name not in ('audio', 'target'):
                    assert np.array_equal(z[name], old[name]), name
            assert np.array_equal(z['orders'], np.arange(1, 289))
            assert not (args.workspace/'references/analysis/waveform_file_real_v1/real1'/row['label']).exists()
            original = z['original_positions']
            positions = np.r_[np.arange(-2048, 0, 256), original, original[-1]+np.arange(256, 2049, 256)]+2048
            assert np.array_equal(z['positions'], positions) and positions[0] == 0 and positions[-1] == len(z['audio'])-1
            oracle, calibration = make(z['audio'], z['metric_target'], positions, z['orders'], z['scale'])
            for name in ('sigma', 'amplitude', 'weights', 'band_power'):
                check('locked_legacy_'+name, z[name], calibration[name])
            assert np.array_equal(z['floor_active'], calibration['floor_active'])
            wave = synthesize(oracle.nodes(z['probe_q'])*z['scale'][None], positions, z['orders'], len(z['audio']))
            check('full288_scalar_probe', z['probe_wave'], wave)
            check('all_bin_probe_spectrum', z['probe_spectrum'], oracle.spectral(wave))
            starts = np.arange(0, len(wave)-4096+1, 256)
            slots = np.where((starts >= 2048) & (starts+4096 <= len(wave)-2048))[0]
            assert np.array_equal(slots, z['target_slots'])
            rows, _ = full_frame(z['target'])
            check('new_target_rows_old_calibration', oracle.profile['rows'][slots], rows[calibration['keep']]*calibration['amplitude'])
            resources = row['resources']
            assert resources['headroom_guard'] == 3*1024**3 and resources['native_temporary_allowance'] == 3*1024**3//2
            assert resources['graph_transpose_three_owned_panels_counted']
            report['cases'].append(dict(label=row['label'], all_qualified=True, orders=288,
                original_nodes=len(original), full_nodes=len(positions), frames=len(wave),
                changed_target_relative_norm=float(np.linalg.norm(z['target']-old['target'])/np.linalg.norm(old['target'])),
                original_calibration_and_context_geometry_exact=True))
            save(args.out/'report.json', report)
            print('AUDIT_LOCKED_PREP', row['label'], 'PASS', flush=True)
        assert source['retained_five_factor_bytes'] == sum(row['resources']['full_factor_disk_bytes'] for row in source['cases'])
        assert sha(repo/'handoff/C文件索引.csv') == source['protected_C_index_sha256']
        report.update(result='independent_locked_source_preparation_verified', all_qualified=True,
            producer_sha256=sha(args.study/'report.json'), no_inverse_or_C_or_sustained_or_hearing_promotion=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
