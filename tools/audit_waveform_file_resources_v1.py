"""Independent known-pipeline native panels, I/O, roots and all regressions."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], inputs={}, root_sources_verified={}, comparisons=[])
    def read(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)
    archive = a.workspace/'baselines/waveform_early_release_v1'
    def input_file(path):
        digest = sha(path)
        if path.is_relative_to(archive):
            assert digest == manifest[path.relative_to(archive).as_posix()]
        r['inputs'][str(path)] = digest
        return path
    def factor(info):
        disk = info['file']
        rows, cols = disk['shape']
        assert rows == info['rows'] and cols == info['columns']
        assert info['retained_directions'] == min(rows, cols)
        assert disk['file_bytes'] == disk['declared_bytes'] == 8*rows*cols
        cap = 8*max(rows, cols)*info['block']
        assert disk['panel_capacity_bytes'] == cap
        assert disk['max_read_buffer_bytes'] <= cap and disk['max_write_panel_bytes'] <= cap
        assert disk['closed'] and not disk['mapped'] and not info['explicit_full_Q']
        path = Path(disk['path'])
        assert path.resolve().is_relative_to(a.study.resolve())
        assert sha(input_file(path)) == disk['sha256']
        assert disk['write_bytes'] >= 8*rows*cols and disk['read_bytes'] > 0
        max_native_panel = max_native_target = max_native_workspace = 0
        for call in info['native_calls']:
            m, n = call['panel_shape']
            assert n <= info['block'] and call['panel_bytes'] == 8*m*n <= cap
            assert call['panel_owned'] and call['panel_Fortran'] and not call['whole_mapped_matrix']
            assert call['output_aliases_input']
            max_native_panel = max(max_native_panel, call['panel_bytes'])
            max_native_workspace = max(max_native_workspace, 8*call['lwork'])
            if call['target_shape'] is not None:
                m2, n2 = call['target_shape']
                assert n2 <= info['block'] and call['target_bytes'] == 8*m2*n2 <= cap
                assert call['target_owned'] and call['target_Fortran']
                max_native_target = max(max_native_target, call['target_bytes'])
        return dict(file=str(path), rows=rows, columns=cols, block=info['block'],
            file_bytes=disk['file_bytes'], read_bytes=disk['read_bytes'], write_bytes=disk['write_bytes'],
            panel_limit_bytes=cap, max_native_panel_bytes=max_native_panel,
            max_native_target_bytes=max_native_target, max_native_work_array_bytes=max_native_workspace,
            native_call_count=len(info['native_calls']), qualified=True)
    try:
        summary = read(repo/'research/waveform_early_release_v1_summary.json')
        assert sha(archive/'manifest.json') == summary['manifest_sha256']
        manifest = {row['path']:row['sha256'] for row in read(archive/'manifest.json')['files']}
        root_audit = read(input_file(archive/'evidence/roots_audit1/report.json'))
        root_producer = read(input_file(archive/'evidence/roots1/report.json'))
        native_audit = read(input_file(archive/'evidence/roots_native_audit1/report.json'))
        assert root_audit['all_qualified'] and len(root_audit['frames']) == 4 and len(root_audit['temporal']) == 3
        assert root_audit['producer_sha256'] == sha(archive/'evidence/roots1/report.json')
        assert native_audit['result'] == 'independent_waveform_banded_controls_passed'
        for name in ('tools/waveform_banded_v1/root.py', 'tools/waveform_banded_v1/metric.py',
                     'tools/waveform_structured_v1/penalty.py', 'tools/waveform_stream_v1/metric_root.py'):
            assert sha(repo/name) == root_producer['sources'][name]
            r['root_sources_verified'][name] = sha(repo/name)
        for kind, folder, count in (('original12', 'known1', 12), ('shared8', 'shared1', 8)):
            produced = read(a.study/folder/'report.json')
            audited = read(a.study/('known_audit1' if kind == 'original12' else 'shared_audit1')/'report.json')
            assert audited['producer_sha256'] == sha(a.study/folder/'report.json')
            assert produced['file_pipeline'] and produced['all_qualified'] and audited['all_qualified']
            assert produced['pass_count'] == audited['pass_count'] == count
            previous = read(input_file(archive/'evidence'/folder/'report.json'))
            indexed = {(c['kind'], c['label']):c for c in previous['cases']}
            for case in produced['cases']:
                flags = case['pipeline_info']
                assert flags['complete_metric_released_before_inverse'] and flags['source_file_closed_before_correction']
                base = flags['base_solver']
                assert base['complete_source_streamed'] and base['source_whitening_rows_streamed']
                assert base['no_dense_X_or_graph_or_square_T_or_full_Q']
                factors = [factor(flags['source']), factor(flags['graph']),
                           factor(case['factor']['right']), factor(case['factor']['inner'])]
                assert factors[0]['columns'] == case['factor']['source_columns']
                ledger = case['resources']
                sizes = ledger['storage_bytes']
                snapshots = [e for e in ledger['events'] if e['event'] == 'snapshot']
                for snap in snapshots:
                    ids = snap['live_storages']
                    assert len(ids) == len(set(ids))
                    assert snap['tracked_live_backing_bytes'] == sum(sizes[j] for j in ids)
                assert max(e['tracked_live_backing_bytes'] for e in snapshots) == ledger['max_tracked_live_backing_bytes']
                assert any(e['phase'] == 'filePipeline.metric_and_base_graph_released' for e in snapshots)
                assert not any(e['name'].startswith('audit_only.full_file_export.source') for e in ledger['events'] if e['event'] == 'array')
                before = indexed[(case['kind'], case['label'])]
                path = a.study/folder/case['file']
                assert sha(input_file(path)) == case['sha256']
                old = input_file(archive/'evidence'/folder/before['file'])
                changes = []
                with np.load(path) as x, np.load(old) as y:
                    for name in ('audio', 'positions', 'orders', 'scale', 'original'):
                        assert np.array_equal(x[name], y[name])
                    for name in ('q', 'z', 'wave_model_residual', 'history_z', 'history_wave', 'history_original_normal', 'delta_z'):
                        assert x[name].shape == y[name].shape
                        changes.append(dict(array=name, bitwise_exact=bool(np.array_equal(x[name], y[name])),
                            max_absolute_difference=float(np.max(abs(x[name]-y[name])))))
                for key in ('dense_relative_error', 'original_gradient', 'stable_complete_normal', 'original_backward'):
                    r['comparisons'].append(dict(kind=kind, label=case['label'], metric=key,
                        previous=before[key], current=case[key], difference=case[key]-before[key],
                        regressed=case[key] > before[key]))
                r['cases'].append(dict(kind=kind, label=case['label'], factors=factors,
                    total_file_bytes=sum(x['file_bytes'] for x in factors),
                    total_read_bytes=sum(x['read_bytes'] for x in factors),
                    total_write_bytes=sum(x['write_bytes'] for x in factors),
                    registered_backing_peak_bytes=ledger['max_tracked_live_backing_bytes'],
                    process_memory=case['process_memory'], elapsed_host_seconds=case['elapsed_seconds'],
                    all_seven_output_array_changes=changes, qualified=True))
        assert len(r['cases']) == 20 and len(r['comparisons']) == 80
        r.update(result='independent_waveform_file_known_resources_verified', all_qualified=True,
            original4DFT_3temporal_native_roots_reused_exact=True,
            no_unregistered_or_native_memory_bound_claim=True,
            no_full_or_real_or_C_or_hearing_qualification=True, auditor_sha256=sha(__file__))
        save(a.out/'report.json', r)
        print(r['result'], 'known', len(r['cases']), 'comparisons', len(r['comparisons']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
