"""Independent scalar-trig/scalar-reflector checks of1024 native file panels."""
import argparse
import math
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
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], maximum_errors={}, inputs={})
    def check(name, x, y):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape
        error = float(np.max(abs(x-y))/max(1., np.max(abs(y))))
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        assert error < 2e-12, (name, error)
    def qmap(raw, tau, value, transpose=False):
        result = np.array(value, copy=True)
        for j in (range(len(tau)) if transpose else range(len(tau)-1, -1, -1)):
            v = np.r_[1., raw[j+1:, j]]
            result[j:] -= v[:, None]*(tau[j]*(v@result[j:]))[None]
        return result
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'waveform_file_large_panels_measured' and source['block'] == 1024
        for name, digest in source['sources'].items():
            assert sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
            r['inputs'][name] = digest
        assert source['preflight']['passed'] and len(source['cases']) == 2
        for case in source['cases']:
            f = case['factor']
            m, n = f['rows'], f['columns']
            assert (m, n) in ((2305, 1537), (1537, 2305))
            disk = f['file']
            path = Path(disk['path'])
            assert path.resolve().is_relative_to(a.study.resolve())
            assert disk['closed'] and not disk['mapped'] and sha(path) == disk['sha256']
            assert disk['file_bytes'] == disk['declared_bytes'] == 8*m*n
            capacity = 8*max(m, n)*1024
            assert disk['panel_capacity_bytes'] == capacity and disk['max_read_buffer_bytes'] <= capacity
            assert disk['max_write_panel_bytes'] <= capacity
            native = f['native_calls']
            assert {call['panel_shape'][1] for call in native if call['kernel'] == 'geqrf'} == {1024, 513}
            for call in native:
                assert call['panel_owned'] and call['panel_Fortran'] and call['output_aliases_input']
                assert not call['whole_mapped_matrix'] and call['panel_shape'][1] <= 1024
                assert call['panel_bytes'] == 8*math.prod(call['panel_shape']) <= capacity
                if call['target_shape'] is not None:
                    assert call['target_owned'] and call['target_Fortran'] and call['target_shape'][1] <= 1024
                    assert call['target_bytes'] == 8*math.prod(call['target_shape']) <= capacity
            # Explicit moderate-only independent audit buffer; never a native
            # production argument or a claim about producer memory bounds.
            raw = np.fromfile(path, dtype='float64').reshape(m, n, order='F')
            cap = a.study/case['file']
            assert sha(cap) == case['sha256']
            with np.load(cap) as z:
                indices, tau = z['indices'], z['tau']
                assert len(tau) == min(m, n)
                expected = np.array([[.03*math.cos(.0031*(i+1)*(int(j)+1))
                    +.02*math.sin(.0023*(2*i+1)*(int(j)+1))
                    +(1+.2*math.cos(int(j)+1) if i == j else 0.)
                    for j in indices] for i in range(m)])
                R = np.zeros_like(expected)
                for column, j in enumerate(indices):
                    R[:min(m, n, int(j)+1), column] = raw[:min(m, n, int(j)+1), j]
                check('selected_complete_R', z['selected_R'], R)
                check('scalar_QR_analytic_columns', qmap(raw, tau, R), expected)
                check('production_QR_analytic_columns', z['roundtrip'], expected)
                check('scalar_forward_Q', z['forward'], qmap(raw, tau, z['rhs']))
                check('scalar_transposed_Q', z['transpose'], qmap(raw, tau, z['rhs'], True))
                check('independent_RHS_energy', z['forward'].T@z['forward'], z['rhs'].T@z['rhs'])
                assert np.count_nonzero(z['forward'][:, -1]) == np.count_nonzero(z['transpose'][:, -1]) == 0
                if m >= n:
                    T = np.triu(raw[:n])
                    check('upper_complete_action', T@z['triangular_exact'], z['triangular_rhs'])
                    check('upper_transpose_complete_action', T.T@z['triangular_exact'], z['triangular_transpose_rhs'])
                    check('upper_complete_solve', z['triangular_forward'], z['triangular_exact'])
                    check('upper_transpose_complete_solve', z['triangular_transpose'], z['triangular_exact'])
            ledger = case['resources']
            for event in ledger['events']:
                if event['event'] == 'array':
                    assert not event['name'].startswith('audit_only.full_file_export')
                elif event['event'] == 'snapshot':
                    ids = event['live_storages']
                    assert len(ids) == len(set(ids))
                    assert event['tracked_live_backing_bytes'] == sum(ledger['storage_bytes'][j] for j in ids)
            r['cases'].append(dict(label=case['label'], qualified=True,
                max_native_panel_bytes=max(c['panel_bytes'] for c in native),
                max_native_target_bytes=max(c['target_bytes'] for c in native),
                max_native_work_array_bytes=max(8*c['lwork'] for c in native),
                registered_backing_peak=ledger['max_tracked_live_backing_bytes'],
                process_memory=case['process_memory'], panel_read_bytes=disk['read_bytes'],
                panel_write_bytes=disk['write_bytes'], factor_sha256=disk['sha256'],
                scalar_original_columns=len(indices), native_calls=len(native)))
        r.update(result='independent_waveform_file_large_panels_verified', all_qualified=True,
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__), block=1024,
            no_full_or_real_or_runtime_qualification=True)
        save(a.out/'report.json', r)
        print(r['result'], 'maxerror', max(r['maximum_errors'].values()), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
