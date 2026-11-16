"""Verify exact stored small blocks, complete actions and cache refusals."""
import argparse
import copy
import os
from pathlib import Path
import shutil
import sys

from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from shared_basis_operator_v1.operator import Operator
    from shared_basis_operator_v1.geometry import Geometry
    from shared_basis_store_v1.identity import specification
    from shared_basis_store_v1.writer import build
    from shared_basis_store_v1.reader import StoredCompiler
    from shared_basis_store_v1.resources import preflight
    from shared_basis_store_v1.study import capture, geometry_args, load_arrays
    from locked_source_guard_v1.measurement import declared

    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[], refusals=[])
    shutil.copy2(__file__, a.out/'executed_probe.py')
    try:
        source, audit = load(a.study/'report.json'), load(a.audit/'report.json')
        assert audit['verification_passed'] and audit['producer_sha256'] == sha(a.study/'report.json')
        r['sources'] = capture(repo, a.out, source, (
            'research/shared_basis_store_v1_plan.json', 'tools/probe_shared_basis_store_v1.py',
            'tools/audit_shared_basis_store_v1.py', 'tools/probe_shared_basis_store_full_v1.py',
            'tools/audit_shared_basis_store_full_v1.py', 'tools/bench_shared_basis_block_v1.py'))
        for path in (a.study/'report.json', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        for case in source['cases']:
            name = case['name']
            original = next(Path(p) for p in source['inputs']
                            if Path(p).parent.name == name and Path(p).name == 'operators.npz')
            assert sha(original) == source['inputs'][str(original)]
            output, blocks = a.study/name/'output.npz', a.study/name/'blocks.npz'
            for path in (original, output, blocks):
                r['inputs'][str(path)] = sha(path)
            assert sha(output) == case['output_sha256'] and sha(blocks) == case['blocks_sha256']
            z, old, expected_blocks = map(load_arrays, (original, output, blocks))
            op = Operator(*geometry_args(z, old['carriers']), cache_bytes=0)
            spec = specification(op.g, repo)
            directory = a.out/name
            directory.mkdir()
            saved = build(directory/'store', op.g, spec, disk_cap=2*1024**3, array_cap=512*1024**2)
            reader = StoredCompiler(saved['root'], op.g, spec, saved['manifest_sha256'])
            entries = 0
            for index in range(len(op.g.starts)):
                ids, matrix = reader.spectral(index)
                assert np.array_equal(ids, expected_blocks['ids_'+str(index)])
                assert np.array_equal(matrix, expected_blocks['matrix_'+str(index)])
                assert not ids.flags.writeable and not matrix.flags.writeable
                entries += matrix.size
            op.compiler = reader
            arrays = dict(source=op.source(z['x']), full_forward=op.full_forward(z['x']),
                          full_adjoint=op.full_adjoint(z['full_dual']),
                          target_adjoint=op.target_adjoint(tuple(z['target_dual_'+str(g)] for g in range(7))),
                          gradient=op.gradient(z['x'], old['rhs']))
            for group, values in enumerate(op.target_forward(z['x'])):
                arrays['target_'+str(group)] = values
            if 'null_full' in old:
                arrays['null_full'] = op.full_forward(z['null_vector'])
            comparisons = {}
            for key, value in arrays.items():
                error = float(np.max(abs(value-old[key])))/max(float(np.max(abs(old[key]))), 1e-300)
                comparisons[key] = error
                assert error <= 2e-11, (name, key, error)
            np.savez_compressed(directory/'output.npz', **arrays)
            r['cases'].append(dict(
                name=name, store=saved, comparisons=comparisons,
                compiled_entries_bitwise_equal_to_audited_blocks=entries,
                output_sha256=sha(directory/'output.npz'),
                loaded_blocks=reader.loaded_blocks, loaded_bytes=reader.loaded_bytes,
                original_direct_metrics=declared(z['audio'], arrays['source'], float(z['amplitude']), z['weights'])))
            save(a.out/'report.json', r)
            print('STORED_SMALL', name, entries, max(comparisons.values()), flush=True)

        base = a.out/r['cases'][0]['name']/'store'
        baseline = r['cases'][0]['store']
        first_original = next(Path(p) for p in source['inputs']
                              if Path(p).parent.name == r['cases'][0]['name'] and Path(p).name == 'operators.npz')
        z = load_arrays(first_original)
        g = Geometry(*geometry_args(z, load_arrays(a.study/r['cases'][0]['name']/'output.npz')['carriers']))
        spec = specification(g, repo)
        control_root = a.out/'refusals'
        control_root.mkdir()

        def reject(name, action):
            try:
                action()
            except (ValueError, FileNotFoundError) as error:
                r['refusals'].append(dict(name=name, error=repr(error)))
                return
            raise AssertionError('Invalid store accepted: '+name)

        def copied(name):
            dest = control_root/name
            shutil.copytree(base, dest)
            return dest

        for label, filename, operation in (
            ('missing_manifest', 'manifest.json', 'delete'),
            ('changed_manifest', 'manifest.json', 'append'),
            ('missing_block', 'block_000_matrix.npy', 'delete'),
            ('truncated_block', 'block_000_matrix.npy', 'truncate'),
            ('matrix_corruption', 'block_000_matrix.npy', 'flip'),
            ('ids_corruption', 'block_000_ids.npy', 'flip'),
            ('header_corruption', 'block_000_matrix.npy', 'header'),
        ):
            root = copied(label)
            path = root/filename
            if operation == 'delete':
                path.unlink()
            elif operation == 'append':
                with path.open('ab') as stream:
                    stream.write(b' ')
            elif operation == 'truncate':
                with path.open('r+b') as stream:
                    stream.truncate(path.stat().st_size-1)
            else:
                with path.open('r+b') as stream:
                    stream.seek(0 if operation == 'header' else -1, 0 if operation == 'header' else 2)
                    position = stream.tell()
                    value = stream.read(1)[0]
                    stream.seek(position)
                    stream.write(bytes([value ^ 1]))
            reject(label, lambda root=root: StoredCompiler(root, g, spec, baseline['manifest_sha256']).spectral(0))
        extra = copied('unexpected_file')
        (extra/'unindexed.pending').write_bytes(b'partial')
        reject('unexpected_file', lambda: StoredCompiler(extra, g, spec, baseline['manifest_sha256']))
        altered = copy.deepcopy(spec)
        altered['runtime']['numpy'] += '-mismatch'
        reject('runtime_identity', lambda: StoredCompiler(base, g, altered, baseline['manifest_sha256']))
        altered = copy.deepcopy(spec)
        altered['sigma_hex'] = (g.sigma*2).hex()
        reject('calibration_identity', lambda: StoredCompiler(base, g, altered, baseline['manifest_sha256']))
        wrong_g = Geometry(*geometry_args(dict(z, sigma=np.array(g.sigma*2)), load_arrays(a.study/r['cases'][0]['name']/'output.npz')['carriers']))
        reject('supplied_geometry_identity', lambda: StoredCompiler(base, wrong_g, spec, baseline['manifest_sha256']))
        reject('disk_cap', lambda: preflight(g, control_root, disk_cap=1, array_cap=512*1024**2))
        reject('array_cap', lambda: preflight(g, control_root, disk_cap=2*1024**3, array_cap=1))
        reject('overwrite', lambda: build(base, g, spec, disk_cap=2*1024**3, array_cap=512*1024**2))
        assert len(r['refusals']) == 14
        r.update(result='synthetic_shared_store_small_controls_completed',
                 original_19_failures_preserved=True, requires_independent_audit=True,
                 no_full_operator_solver_or_vehicle_fidelity_qualification=True,
                 no_actual_source_or_new_audio_C=True)
        save(a.out/'report.json', r)
        print(r['result'], len(r['refusals']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
