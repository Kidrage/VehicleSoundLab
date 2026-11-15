"""Known correction lifetimes, experimental native triangles, conditional sizes.

No full/source allocation. Native LAPACK accesses the existing 2k-by-k QR with
lda=2k; this optional probe does not select it for the corrected solver.
"""
import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'audit', 'shared', 'shared-audit', 'context', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import scipy
    from scipy import linalg
    from waveform_correction_v1.native_triangular import NativeUpperTriangular
    from run_waveform_stream_full_v1 import physical_memory
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helper = 'tools/waveform_correction_v1/native_triangular.py'
    shutil.copy2(repo/helper, a.out/'executed_native_triangular.py')
    r = dict(result='running', cases=[], native_replays=[], conditional_cases=[], inputs={},
             dependencies=dict(numpy=np.__version__, scipy=scipy.__version__),
             native_probe_factory_selected=False)

    def read(folder):
        path = folder/'report.json'; r['inputs'][str(path)] = sha(path)
        return load(path)

    def digest(array):
        return hashlib.sha256(array.tobytes(order='F')).hexdigest()

    rng = np.random.default_rng(671403)

    def probe(raw, k, label):
        assert raw.flags.f_contiguous
        before = digest(raw); raw.flags.writeable = False
        triangle = np.triu(raw[:k]).copy()
        native = NativeUpperTriangular(raw, k)
        errors = []
        for transpose in (False, True):
            rhs = np.array(rng.normal(size=(k, 3)), order='F')
            original = rhs.copy(); pointer = rhs.ctypes.data
            expected = linalg.solve_triangular(triangle, rhs, trans='T' if transpose else 'N')
            out = native.solve_inplace(rhs, transpose)
            assert out is rhs and out.ctypes.data == pointer
            error = float(np.linalg.norm(out-expected)/max(np.linalg.norm(expected), 1e-300))
            backward = float(np.linalg.norm((triangle.T if transpose else triangle) @ out-original)
                             / max(np.linalg.norm(triangle)*np.linalg.norm(out)+np.linalg.norm(original), 1e-300))
            assert error < 2e-12 and backward < 1e-11, (label, error, backward)
            errors.append(dict(transpose=transpose, relative_error=error, backward=backward))
        assert digest(raw) == before
        r['native_replays'].append(dict(label=label, raw_shape=list(raw.shape), triangle_size=k,
            leading_dimension=raw.shape[0], native_pointer_aliases_existing_QR=bool(native.raw is raw),
            matrix_readonly_and_unchanged=True, RHS_inplace=True, results=errors,
            ABI=native.signature, no_square_triangle_in_native_module=True))

    try:
        known, ka, shared, sa, context = [read(path) for path in
            (a.known, a.audit, a.shared, a.shared_audit, a.context)]
        for folder, source, audit, count in ((a.known, known, ka, 12), (a.shared, shared, sa, 8)):
            assert audit['result'] == 'independent_waveform_original_correction_known_verified'
            assert audit['all_qualified'] and audit['pass_count'] == count
            assert audit['producer_sha256'] == sha(folder/'report.json')
            for case in source['cases']:
                path = folder/case['file']; assert sha(path) == case['sha256']
                r['inputs'][str(path)] = sha(path)
                events, stores = case['resources']['events'], case['resources']['storage_bytes']
                arrays = {e['name']: e for e in events if e['event'] == 'array'}
                snapshots = [e for e in events if e['event'] == 'snapshot']
                for e in arrays.values():
                    assert e['dtype'] == 'float64' and e['bytes'] == 8*np.prod(e['shape'])
                    assert e['backing_bytes'] == stores[e['storage']]
                for e in snapshots:
                    assert len(e['live_storages']) == len(set(e['live_storages']))
                    assert e['tracked_live_backing_bytes'] == sum(stores[j] for j in e['live_storages'])
                for prefix, name in (('correction.right_QR', 'correction.right_input'),
                                     ('correction.inner_QR', 'correction.inner_input')):
                    assert arrays[prefix+'.raw']['storage'] == arrays[name]['storage']
                    assert arrays[prefix+'.reflectors']['storage'] == arrays[name]['storage']
                    assert prefix+'.R' not in arrays
                assert arrays['correction.inner_QR.square_R']['storage'] != arrays['correction.inner_QR.raw']['storage']
                peak = max(e['tracked_live_backing_bytes'] for e in snapshots)
                assert peak == case['resources']['max_tracked_live_backing_bytes']
                r['cases'].append(dict(kind=case['kind'], label=case['label'],
                    registered_backing_peak=peak,
                    base_X_bytes=arrays['base.x_raw']['bytes'],
                    inverse_right_bytes=arrays['correction.right_QR.raw']['bytes'],
                    inverse_inner_bytes=arrays['correction.inner_QR.raw']['bytes'],
                    explicit_T_copy_bytes=arrays['correction.inner_QR.square_R']['bytes'],
                    actual_cumulative_process_peak=case['process_memory']['cumulative_peak_working_set_bytes']))
                with np.load(path) as z:
                    raw = z['inverse_inner_raw']; k = len(z['inverse_inner_tau'])
                    probe(raw, k, ('known' if source is known else 'shared')+'_'+case['label'])
        # Additional non-power-of-two leading dimensions and reflector-like
        # lower entries, including padding below the square upper triangle.
        for k, extra in ((1, 3), (7, 11), (23, 5)):
            raw = np.array(rng.normal(size=(k+extra, k)), order='F')
            raw[np.arange(k), np.arange(k)] += k+1
            probe(raw, k, 'padded_'+str(k))
        rejections = []
        for label, raw, size in (
            ('float32', np.eye(3, dtype=np.float32, order='F'), 3),
            ('C_order', np.ones((7, 3)), 3),
            ('oversized_triangle', np.ones((7, 3), order='F'), 4),
            ('nonfinite_upper', np.full((7, 3), np.nan, order='F'), 3),
        ):
            try:
                NativeUpperTriangular(raw, size)
            except ValueError:
                rejections.append(label)
            else:
                raise AssertionError(('invalid native matrix accepted', label))
        zero = np.zeros((6, 3), order='F')
        try:
            NativeUpperTriangular(zero, 3).solve_inplace(np.ones((3, 2), order='F'))
        except ArithmeticError as error:
            assert error.args[0] == ('native dtrtrs', 1)
            rejections.append('singular_info_1')
        else:
            raise AssertionError('Singular native triangle accepted')
        memory = physical_memory(); r['available_memory'] = memory

        def budget(N, M, label):
            n = 2*M*288; k = min(N, n)
            base = dict(W_band=8*4096*N, X_raw=8*N*n, graph_raw=8*(k+n)*k, graph_T=8*k*k)
            correction = dict(X_raw=8*N*n, inverse_right=8*n*k,
                              inverse_inner=8*2*k*k, inverse_T=8*k*k)
            base_bytes, correction_bytes = sum(base.values()), sum(correction.values())
            # Keep all four old factors unless an integrated release/reload
            # path is implemented and independently shown at actual scale.
            retained = base_bytes+sum(v for name, v in correction.items() if name != 'X_raw')
            separate = max(base_bytes, correction_bytes)
            native_separate = max(base_bytes, correction_bytes-correction['inverse_T'])
            reserve, headroom = 3*1024**3//2, 3*1024**3
            free = min(memory['available_physical_bytes'], memory['available_commit_bytes'])
            def row(main):
                required = main+reserve+headroom
                return dict(main_arrays_only=main, required_available=required,
                            available_memory_gate_passed=bool(free >= required))
            return dict(label=label, frames=N, nodes=M, orders=288, independent_RHS=2,
                base_arrays=base, correction_arrays=correction,
                all_old_factors_retained=row(retained),
                proposed_separate_phases=row(separate),
                proposed_separate_phases_native_triangle=row(native_separate),
                native_and_temporary_allowance_bytes=reserve, unchanged_headroom_bytes=headroom,
                square_T_bytes_potentially_avoided=correction['inverse_T'],
                integrated_release_or_native_solver_implemented=False,
                conditional_only_not_allocated=True, peak_memory_or_feasibility_NOT_proven=True)

        r['conditional_cases'].append(budget(12289, 49, 'full_known'))
        for c in context['cases']:
            r['conditional_cases'].extend((budget(c['frames'], c['nodes'], c['label']+' original'),
                budget(c['frames']+4096, c['nodes']+16, c['label']+' proposed_context')))
        assert len(r['cases']) == 20 and len(r['native_replays']) == 23 and len(rejections) == 5
        r.update(result='independent_waveform_correction_resources_inspected',
            original12_cumulative_process_peak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in known['cases']),
            shared8_cumulative_process_peak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in shared['cases']),
            native_rejections=rejections, auditor_sha256=sha(__file__), native_module_sha256=sha(repo/helper),
            scope='Registered factor arrays and separately measured known-process cumulative peaks; unregistered caller/evaluator/library temporaries excluded from ledger. Conditional phase arithmetic is not actual full peak.',
            full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], 'native replays', len(r['native_replays']), flush=True)
        for c in r['conditional_cases']:
            print(c['label'], c['proposed_separate_phases'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
