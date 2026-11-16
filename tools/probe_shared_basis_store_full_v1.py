"""One complete shared-method synthetic known operator with immutable disk blocks."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time

from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'legacy', 'legacy-audit', 'cache', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1.oracle import table, full
    from shared_basis_operator_v1.operator import Operator
    from shared_basis_store_v1.study import capture, geometry_args, load_arrays
    from shared_basis_store_v1.identity import specification
    from shared_basis_store_v1.writer import build
    from shared_basis_store_v1.reader import StoredCompiler
    from locked_source_guard_v1.measurement import declared, fidelity
    from waveform_structured_v1.resources import process_memory

    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, phases={})
    try:
        small, proof = load(a.study/'report.json'), load(a.audit/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(a.study/'report.json')
        assert proof['total_compiled_entries_verified'] == 2622720 and proof['refusals_verified'] == 14
        r['sources'] = capture(repo, a.out, small, ())
        for path in (a.study/'report.json', a.audit/'report.json', a.legacy/'report.json', a.legacy_audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        old, legacy_audit = load(a.legacy/'report.json'), load(a.legacy_audit/'report.json')
        assert legacy_audit['producer_sha256'] == sha(a.legacy/'report.json')
        assert not legacy_audit['verification_passed'] and len(legacy_audit['failures']) == 19
        name = 'full288_73_AM_PM_sweep_weak'
        original = next(c for c in old['cases'] if c['name'] == name)
        prior_proof = next(c for c in legacy_audit['cases'] if c['name'] == name)
        assert not any(c['case'] == name for c in legacy_audit['failures'])
        assert prior_proof['maximum_scaled_error'] < 2e-11
        packet = a.legacy/name/'operators.npz'
        assert sha(packet) == original['packet_sha256']
        r['inputs'][str(packet)] = sha(packet)
        z = load_arrays(packet)
        op = Operator(*geometry_args(z, table(z['orders'])), cache_bytes=0)
        assert (op.g.frames, len(op.g.positions), len(op.g.orders), op.size) == (18430, 73, 288, 84096)
        a.cache.parent.mkdir(parents=True, exist_ok=True)
        spec = specification(op.g, repo)
        save(a.out/'specification.json', spec)

        def progress(done, total):
            r['active_phase'] = dict(name='compiling', completed_blocks=done, total_blocks=total)
            save(a.out/'report.json', r)
            if done % 8 == 0 or done == total:
                print('FULL_STORE_COMPILED', done, total, flush=True)

        started = time.perf_counter()
        r['store'] = build(a.cache, op.g, spec, disk_cap=24*1024**3, array_cap=1024**3, progress=progress)
        r['phases']['compile_and_publish_seconds'] = time.perf_counter()-started
        reader = StoredCompiler(a.cache, op.g, spec, r['store']['manifest_sha256'])
        op.compiler = reader
        arrays = dict(carriers=op.g.carriers, rhs=full(z, z['audio']))

        def action(label, function):
            r['active_phase'] = dict(name=label, loaded_blocks=reader.loaded_blocks)
            save(a.out/'report.json', r)
            started = time.perf_counter()
            value = function()
            r['phases'][label+'_seconds'] = time.perf_counter()-started
            print('FULL_STORED_ACTION', label, r['phases'][label+'_seconds'], flush=True)
            return value

        arrays['source'] = action('source', lambda: op.source(z['x']))
        arrays['full_forward'] = action('full_forward', lambda: op.full_forward(z['x']))
        arrays['full_adjoint'] = action('full_adjoint', lambda: op.full_adjoint(z['full_dual']))
        target = action('target_forward', lambda: op.target_forward(z['x']))
        for group, value in enumerate(target):
            arrays['target_'+str(group)] = value
        arrays['target_adjoint'] = action('target_adjoint', lambda: op.target_adjoint(tuple(z['target_dual_'+str(g)] for g in range(7))))
        arrays['gradient'] = action('gradient_from_saved_forward_residual',
                                    lambda: op.full_adjoint(arrays['full_forward']-arrays['rhs'])+op.prior.apply(z['x']))
        error_full = float(abs(arrays['full_forward']@z['full_dual']-z['x']@arrays['full_adjoint']))
        dot_full = error_full/max(float(np.linalg.norm(arrays['full_forward'])*np.linalg.norm(z['full_dual'])), 1e-300)
        dot_target = float(abs(sum(target[g]@z['target_dual_'+str(g)] for g in range(7))-z['x']@arrays['target_adjoint']))
        dot_target /= max(float(np.linalg.norm(z['x'])*np.linalg.norm(arrays['target_adjoint'])), 1e-300)
        assert max(dot_full, dot_target) < 2e-11
        metrics = declared(z['audio'], arrays['source'], float(z['amplitude']), z['weights'])
        np.savez_compressed(a.out/'output.npz', **arrays)
        shutil.copy2(a.cache/'manifest.json', a.out/'cache_manifest.json')
        residual = arrays['full_forward']-arrays['rhs']
        r.pop('active_phase', None)
        r.update(result='full_synthetic_stored_shared_operator_executed',
                 output_sha256=sha(a.out/'output.npz'), specification_sha256=sha(a.out/'specification.json'),
                 full_dot_scaled_error=dot_full, target_dot_scaled_error=dot_target,
                 original_direct_metrics=metrics, synthetic_direct_fidelity_passed=fidelity(metrics),
                 objective=float(.5*residual@residual+op.prior.cost(z['x'])),
                 loaded_blocks=reader.loaded_blocks, loaded_bytes=reader.loaded_bytes,
                 process_memory=process_memory(), no_dense_full_matrix_or_actual_D_factors=True,
                 original_19_failures_preserved=True, independent_full_audit_required=True,
                 constrained_solver_not_implemented_or_qualified=True,
                 actual_vehicle_source_statistical_or_audio_C_qualification=False)
        save(a.out/'report.json', r)
        print(r['result'], reader.loaded_blocks, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
