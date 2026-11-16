"""Independently read every stored small entry and compare saved action outputs."""
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
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_guard_v1.measurement import declared
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], auditor_sha256=sha(__file__))
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'synthetic_shared_store_small_controls_completed'
        repo = Path(__file__).resolve().parents[1]
        for name, expected in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in source['inputs'].items():
            assert sha(name) == expected
        def arrays(path):
            with np.load(path, allow_pickle=False) as stream:
                return {key: stream[key] for key in stream.files}
        for case in source['cases']:
            name = case['name']
            original_blocks = next(Path(p) for p in source['inputs'] if Path(p).parent.name == name and Path(p).name == 'blocks.npz')
            original_output = original_blocks.with_name('output.npz')
            original_packet = next(Path(p) for p in source['inputs'] if Path(p).parent.name == name and Path(p).name == 'operators.npz')
            z, expected, old = map(arrays, (original_packet, original_blocks, original_output))
            store = Path(case['store']['root'])
            assert sha(store/'manifest.json') == case['store']['manifest_sha256']
            manifest = load(store/'manifest.json')
            elements = 0
            for block in manifest['blocks']:
                for key in ('ids', 'matrix'):
                    info = block[key]
                    path = store/info['file']
                    assert path.stat().st_size == info['bytes'] and sha(path) == info['file_sha256']
                    value = np.load(path, allow_pickle=False)
                    reference = expected[key+'_'+str(block['index'])]
                    assert np.array_equal(value, reference)
                    if key == 'matrix':
                        elements += value.size
            assert elements == case['compiled_entries_bitwise_equal_to_audited_blocks']
            output = a.study/name/'output.npz'
            assert sha(output) == case['output_sha256']
            results = arrays(output)
            worst = 0.
            for key, value in results.items():
                error = float(np.max(abs(value-old[key])))/max(float(np.max(abs(old[key]))), 1e-300)
                assert error == case['comparisons'][key] and error <= 2e-11
                worst = max(worst, error)
            assert declared(z['audio'], results['source'], float(z['amplitude']), z['weights']) == case['original_direct_metrics']
            r['cases'].append(dict(name=name, compiled_entries_verified=elements,
                                  action_elements_verified=sum(v.size for v in results.values()),
                                  maximum_scaled_error=worst))
        # Inspect the actual mutated files, not just the count of refusal labels.
        root = a.study/'refusals'
        base = Path(source['cases'][0]['store']['root'])
        assert not (root/'missing_manifest/manifest.json').exists()
        assert sha(root/'changed_manifest/manifest.json') != sha(base/'manifest.json')
        assert not (root/'missing_block/block_000_matrix.npy').exists()
        for label, filename in (('truncated_block', 'block_000_matrix.npy'),
                                ('matrix_corruption', 'block_000_matrix.npy'),
                                ('ids_corruption', 'block_000_ids.npy'),
                                ('header_corruption', 'block_000_matrix.npy')):
            assert sha(root/label/filename) != sha(base/filename)
        assert (root/'unexpected_file/unindexed.pending').is_file()
        assert {v['name'] for v in source['refusals']} == {
            'missing_manifest', 'changed_manifest', 'missing_block', 'truncated_block',
            'matrix_corruption', 'ids_corruption', 'header_corruption', 'unexpected_file',
            'runtime_identity', 'calibration_identity', 'supplied_geometry_identity',
            'disk_cap', 'array_cap', 'overwrite'}
        r.update(result='synthetic_shared_store_small_controls_verified', verification_passed=True,
                 producer_sha256=sha(a.study/'report.json'), refusals_verified=14,
                 total_compiled_entries_verified=sum(v['compiled_entries_verified'] for v in r['cases']),
                 maximum_scaled_error=max(v['maximum_scaled_error'] for v in r['cases']),
                 full_operator_or_solver_or_actual_source_qualification=False)
        save(a.out/'report.json', r)
        print(r['result'], r['total_compiled_entries_verified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
