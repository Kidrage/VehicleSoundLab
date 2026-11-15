"""Independent scalar QR/actions, disk layout, native buffer and rejection audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'numeric-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_structured_v1.resources import ArrayLedger
    from waveform_file_v1.store import FileMatrix
    from waveform_file_v1.factor import FileQR
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', kernel_cases=[], file_cases=[], guards=[], maximum_errors={})
    def check(name, x, y, gate=2e-12):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape
        error = float(np.max(abs(x-y))/max(1., abs(y).max()))
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        assert error < gate, (name, error)
    def qmap(raw, tau, value, transpose=False):
        result = np.array(value, copy=True)
        for j in (range(len(tau)) if transpose else range(len(tau)-1, -1, -1)):
            v = np.r_[1., raw[j+1:, j]]
            result[j:] -= v[:, None]*(tau[j]*(v@result[j:]))[None]
        return result
    def inspect_factor(factor):
        disk = factor['file']
        assert disk['closed'] and not disk['mapped'] and disk['dtype'] == 'float64' and disk['order'] == 'F'
        rows, cols = disk['shape']
        capacity = 8*max(rows, cols)*factor['block']
        assert disk['file_bytes'] == disk['declared_bytes'] == 8*rows*cols
        assert disk['panel_capacity_bytes'] == capacity
        assert disk['max_read_buffer_bytes'] <= capacity and disk['max_write_panel_bytes'] <= capacity
        path = Path(disk['path'])
        assert path.resolve().is_relative_to(a.study.resolve()) and sha(path) == disk['sha256']
        assert disk['read_bytes'] > 0 and disk['write_bytes'] >= disk['file_bytes']
        assert factor['retained_directions'] == min(rows, cols)
        assert not factor['explicit_full_Q'] and factor['full_R_and_reflectors_on_disk']
        for call in factor['native_calls']:
            m, n = call['panel_shape']
            assert call['panel_owned'] and call['panel_Fortran'] and call['panel_bytes'] == 8*m*n <= capacity
            assert n <= factor['block'] and not call['whole_mapped_matrix'] and call['output_aliases_input']
            if call['target_shape'] is not None:
                m2, n2 = call['target_shape']
                assert call['target_owned'] and call['target_Fortran'] and n2 <= factor['block']
                assert call['target_bytes'] == 8*m2*n2 <= capacity
                assert call['kernel'] in ('ormqr_N', 'ormqr_T', 'trtrs_N', 'trtrs_T')
            else:
                assert call['kernel'] == 'geqrf'
        return dict(path=str(path), native_calls=len(factor['native_calls']),
            capacity_bytes=capacity, largest_read_panel_bytes=disk['max_read_buffer_bytes'],
            read_bytes=disk['read_bytes'], write_bytes=disk['write_bytes'], qualified=True)
    try:
        source = load(a.study/'report.json')
        numeric = load(a.numeric_audit/'report.json')
        assert source['file_kernel_stage'] and not source['whole_file_mapping']
        assert numeric['all_qualified'] and numeric['producer_sha256'] == sha(a.study/'report.json')
        assert len(numeric['inverse_cases']) == 8 and len(numeric['original_cases']) == 7
        for name, digest in source['sources'].items():
            assert sha(a.study/'exact_sources'/name) == digest
        for case in source['kernel_cases']:
            path = a.study/case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z:
                X, raw, tau, rhs = (z[name] for name in ('X', 'x_raw', 'x_tau', 'rhs'))
                m, n = X.shape
                Q = qmap(raw, tau, np.eye(m))
                check('complete_Q_orthogonality', Q.T@Q, np.eye(m))
                R = np.zeros((m, n))
                R[:min(m, n)] = np.triu(raw[:min(m, n)])
                check('full_QR_identity', Q@R, X)
                check('Q_all_basis_independent_RHS', z['forward'], Q@rhs)
                check('QT_all_basis_independent_RHS', z['transpose'], Q.T@rhs)
                assert np.count_nonzero(z['forward'][:, -1]) == np.count_nonzero(z['transpose'][:, -1]) == 0
                if m >= n:
                    T = np.triu(raw[:n])
                    check('complete_upper_solve', z['triangular_forward'], linalg.solve_triangular(T, z['triangular_rhs']))
                    check('complete_upper_transpose_solve', z['triangular_transpose'], linalg.solve_triangular(T, z['triangular_rhs'], trans='T'))
                disk = np.fromfile(case['factor']['file']['path'], dtype='float64').reshape(m, n, order='F')
                assert np.array_equal(disk, raw)
            r['kernel_cases'].append(dict(label=case['label'], **inspect_factor(case['factor'])))
        for case in source['inverse_cases'] + source['original_cases']:
            records = [inspect_factor(case['source_factor']), inspect_factor(case['factor']['right']), inspect_factor(case['factor']['inner'])]
            if 'graph_factor' in case:
                records.append(inspect_factor(case['graph_factor']))
            for record in case['files']:
                path = a.study/record['file']
                assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256']
            ledger = case['resources']
            sizes = ledger['storage_bytes']
            for event in ledger['events']:
                if event['event'] == 'snapshot':
                    ids = event['live_storages']
                    assert len(ids) == len(set(ids))
                    assert event['tracked_live_backing_bytes'] == sum(sizes[j] for j in ids)
            r['file_cases'].append(dict(label=case['label'], factors=records, qualified=True))
        ledger = ArrayLedger()
        store = FileMatrix(a.out/'guards.bin', (7, 9), 2, ledger)
        valid = np.arange(63, dtype='float64').reshape(7, 9, order='F')
        for j in range(0, 9, 2):
            stop = min(j+2, 9)
            store.write(0, 7, j, stop, valid[:, j:stop])
        def rejects(name, operation):
            try:
                operation()
            except (ValueError, FileExistsError):
                r['guards'].append(dict(name=name, rejected=True))
            else:
                raise AssertionError(('Guard accepted invalid input', name))
        rejects('full_read_exceeds_panel', lambda:store.read(0, 7, 0, 9))
        rejects('negative_region', lambda:store.read(-1, 2, 0, 1))
        rejects('empty_region', lambda:store.read(0, 0, 0, 1))
        rejects('float_indices', lambda:store.read(0., 1, 0, 1))
        rejects('overwrite_existing_file', lambda:FileMatrix(store.path, (7, 9), 2, ledger))
        rejects('nonfinite_write', lambda:store.write(0, 1, 0, 1, np.array([[np.nan]])))
        rejects('shape_mismatch_write', lambda:store.write(0, 1, 0, 1, np.ones((1, 2))))
        rejects('unowned_native_panel', lambda:FileQR._owned(np.ones((4, 4), order='F')[:, :2]))
        rejects('C_order_native_panel', lambda:FileQR._owned(np.ones((4, 3), order='C')))
        rejects('nonfinite_native_panel', lambda:FileQR._owned(np.array([[np.nan]], order='F')))
        rejects('large_dense_source_builder', lambda:FileMatrix.from_array(a.out/'too_big.bin', np.ones((513, 2)), 2, ledger))
        store.close()
        rejects('closed_read', lambda:store.read(0, 1, 0, 1))
        assert len(r['kernel_cases']) == 12 and len(r['file_cases']) == 15 and len(r['guards']) == 12
        r.update(result='independent_waveform_file_panels_known_verified', all_qualified=True,
            producer_sha256=sha(a.study/'report.json'), numeric_audit_sha256=sha(a.numeric_audit/'report.json'),
            auditor_sha256=sha(__file__), whole_file_mapping=False,
            explicit_native_buffer_bounds_verified=True,
            no_full_pipeline_or_real_or_C_or_hearing_qualification=True)
        save(a.out/'report.json', r)
        print(r['result'], 'kernels', len(r['kernel_cases']), 'guards', len(r['guards']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
