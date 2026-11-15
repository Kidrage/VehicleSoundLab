"""Same12 stable solver fixtures using actual disk-mapped float64 bases."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'prerequisite', 'previous', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_representer_v1.fixtures import DenseFixture
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_inverse_v1.fit import complex_array
    from krylov_diagnostic_v1.mapped_solver import infer, release_basis
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, cases=[], material_read=False)
    try:
        gate = load(a.prerequisite/'report.json')
        assert gate['result'] == 'independent_observer_stable_controls_passed'
        previous = load(a.previous/'report.json')
        assert previous['result'] == 'independent_observer_reorth_known_passed' and not previous['all_qualified']
        r['inputs'][str(a.previous/'report.json')] = sha(a.previous/'report.json')
        r['inputs'][str(a.prerequisite/'report.json')] = sha(a.prerequisite/'report.json')
        parents = {}
        for kind, folder in (('algebra', 'primal_algebra1'), ('Hann', 'context1')):
            parents[kind] = (a.original/folder, load(a.original/folder/'report.json'))
            assert parents[kind][1]['all_qualified']
            r['inputs'][str(a.original/folder/'report.json')] = sha(a.original/folder/'report.json')
        names = set(n for _, parent in parents.values() for n in parent['sources'])
        names.update(('tools/run_observer_stable_mapped_known_v1.py', 'tools/krylov_diagnostic_v1/reorth.py',
            'tools/krylov_diagnostic_v1/stable_residual.py', 'tools/krylov_diagnostic_v1/mapped_solver.py',
            'research/observer_stable_mapped_v1_plan.json',
            'research/observer_stable_residual_v1_plan.json'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        for kind, (folder, parent) in parents.items():
            for old in parent['cases']:
                path = folder/old['file']
                assert sha(path) == old['sha256']
                r['inputs'][str(path)] = sha(path)
                with np.load(path) as z:
                    if kind == 'algebra':
                        system = DenseFixture(old['channels'], old['weak'], old['silent_right'])
                        assert np.array_equal(system.A, z['A']) and np.array_equal(system.audio, z['audio'])
                        audio = system.audio
                        original = complex_array(z['original'], system.nshape)*system.scale[None]
                    else:
                        audio, positions, orders, scale = (z[n] for n in ('audio', 'positions', 'orders', 'scale'))
                        system = SupportedSystem(WaveSynthesis(len(audio), positions, orders, 1), scale, SupportedMetric(audio, 64.))
                        original = z['original_dense_nodes']
                fitted, u, info, residual_cert, repr_cert, capture = infer(system, audio, basis_directory=a.out/(kind+'_'+Path(old['file']).stem+'_basis'))
                error = float(np.linalg.norm((fitted-original)/system.scale[None])/np.linalg.norm(original/system.scale[None]))
                qualified = bool(error < 2e-7 and info['converged'] and residual_cert['additional_gap_gate_passed']
                    and repr_cert['additional_gap_gate_passed'])
                capture.update(fitted=fitted, u=u, original=original, scale=system.scale)
                dest = a.out/(kind+'_'+old['file'])
                np.savez_compressed(dest, **capture)
                release_basis(capture, info)
                r['cases'].append(dict(kind=kind, label=old['label'], original_file=str(path),
                    file=dest.name, sha256=sha(dest), solver=info, dense_relative_error=error,
                    residual_certificate=residual_cert, representer_certificate=repr_cert, qualified=qualified))
                save(a.out/'report.json', r)
                print(kind, old['label'], qualified, 'directions', info['iterations'], 'stop', info['stop'],
                    'node', error, 'gradient', info['relative_stationarity'], flush=True)
        assert len(r['cases']) == 12
        r.update(result='observer_stable_known_measured', all_qualified=all(c['qualified'] for c in r['cases']),
            complete_full_solve_or_source_or_C_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
