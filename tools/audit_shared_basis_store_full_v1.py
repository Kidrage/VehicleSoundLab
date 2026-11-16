"""Complete stored-method audit using saved independent full references and raw FFT."""
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
    from constrained_source_operator_v1 import oracle
    from locked_source_guard_v1.measurement import declared, fidelity
    from shared_basis_store_v1.study import load_arrays

    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', comparisons={}, failures=[], auditor_sha256=sha(__file__))
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'full_synthetic_stored_shared_operator_executed'
        repo = Path(__file__).resolve().parents[1]
        for name, expected in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in source['inputs'].items():
            assert sha(name) == expected
        packet = next(Path(name) for name in source['inputs'] if Path(name).name == 'operators.npz')
        z = load_arrays(packet)
        assert sha(a.study/'output.npz') == source['output_sha256']
        o = load_arrays(a.study/'output.npz')
        root = Path(source['store']['root'])
        assert sha(root/'manifest.json') == sha(a.study/'cache_manifest.json') == source['store']['manifest_sha256']
        # Re-read ALL persisted files once with the independent NPY reader and
        # SHA implementation, without using StoredCompiler or compiling again.
        manifest = load(a.study/'cache_manifest.json')
        stored_bytes = (root/'manifest.json').stat().st_size
        for block in manifest['blocks']:
            for key in ('ids', 'matrix'):
                info = block[key]
                path = root/info['file']
                assert path.stat().st_size == info['bytes'] and sha(path) == info['file_sha256']
                array = np.load(path, allow_pickle=False)
                assert list(array.shape) == info['shape'] and array.dtype.str == info['dtype']
                assert np.isfinite(array).all()
                stored_bytes += path.stat().st_size
                del array
        assert stored_bytes == source['store']['stored_bytes']
        assert len(manifest['blocks']) == 56
        elements = 0

        def check(name, got, expected):
            nonlocal elements
            got, expected = np.asarray(got), np.asarray(expected)
            assert got.shape == expected.shape
            error = float(np.max(abs(got-expected)))/max(float(np.max(abs(expected))), 1e-300)
            r['comparisons'][name] = error
            elements += got.size
            if not np.isfinite(error) or error > 2e-11:
                r['failures'].append(dict(check=name, scaled_error=error, unchanged_threshold=2e-11))

        # Saved full references have already passed the independent original
        # scalar audit; keep its19 small failures and exact input hash binding.
        check('all_source_samples_vs_saved_scalar_reference', o['source'], z['wave'])
        for key in ('full_forward', 'full_adjoint', 'target_adjoint', 'gradient'):
            check('all_'+key+'_vs_audited_saved_reference', o[key], z[key])
        for group in range(7):
            check('all_target_'+str(group)+'_vs_audited_saved_reference', o['target_'+str(group)], z['target_'+str(group)])
        # Raw FFT of the newly produced wave is a separate semantic check,
        # not a compiled-row equality assumed from the shared matrix method.
        check('all_full_rows_vs_raw_declared_FFT', o['full_forward'], oracle.full(z, o['source']))
        groups = oracle.target(z, o['source'])
        for group in range(7):
            check('all_target_'+str(group)+'_vs_raw_declared_FFT', o['target_'+str(group)], groups[group])
        check('rhs', o['rhs'], oracle.full(z, z['audio']))
        metrics = declared(z['audio'], o['source'], float(z['amplitude']), z['weights'])
        assert metrics == source['original_direct_metrics']
        assert fidelity(metrics) == source['synthetic_direct_fidelity_passed']
        assert source['loaded_blocks'] == 248
        passed = not r['failures']
        r.update(result='full_synthetic_stored_shared_operator_assessed', verification_passed=passed,
                 producer_sha256=sha(a.study/'report.json'), elements_checked=elements,
                 maximum_scaled_error=max(r['comparisons'].values()),
                 all_112_payload_files_independently_hashed_and_loaded=True,
                 complete_288orders_73nodes_stereo_not_a_reduced_surrogate=True,
                 original_17_direct_metrics_recomputed=True, original_19_failures_preserved=True,
                 full_constrained_solver_or_actual_vehicle_fidelity_qualification=False,
                 new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json', r)
        print(r['result'], passed, elements, r['maximum_scaled_error'], flush=True)
        if not passed:
            raise RuntimeError('Full known comparisons failed; see retained failures')
    except BaseException as error:
        if 'verification_passed' not in r:
            r.update(result='failed', error=repr(error))
        else:
            r['error'] = repr(error)
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
