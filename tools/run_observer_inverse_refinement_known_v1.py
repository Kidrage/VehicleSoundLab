"""Known-first same-objective correction, with two nonoptimal starts per RHS."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'known-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.fit import RegularizedObserver, real_vector, complex_array
    from observer_inverse_v1.precondition import RightMap
    from observer_inverse_v1.refinement import SavedRightMap, refine
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], inputs={}, sources={}, material_read=False)
    names = ('tools/run_observer_inverse_refinement_known_v1.py',
        'tools/observer_forward_v1/operator.py', 'tools/observer_forward_v1/polyphase.py',
        'tools/observer_inverse_v1/fit.py', 'tools/observer_inverse_v1/regularizer.py',
        'tools/observer_inverse_v1/precondition.py', 'tools/observer_inverse_v1/refinement.py')
    try:
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        old, audit = load(a.known/'report.json'), load(a.known_audit/'report.json')
        assert audit['result'] == 'independent_observer_inverse_known_passed'
        assert audit['producer_sha256'] == sha(a.known/'report.json')
        for name in ('report.json', 'dense_system.npz'):
            r['inputs'][str(a.known/name)] = sha(a.known/name)
        r['inputs'][str(a.known_audit/'report.json')] = sha(a.known_audit/'report.json')
        assert sha(a.known/'dense_system.npz') == old['dense_sha256']
        shutil.copy2(a.known/'dense_system.npz', a.out/'dense_system.npz')
        with np.load(a.known/'dense_system.npz') as z:
            cap = {k:z[k] for k in z.files}
        op = PolyphaseObserver(int(cap['frames']), cap['positions'], cap['orders'], cap['orders'])
        system = RegularizedObserver(op, cap['scale'])
        right = RightMap(system)
        restored = SavedRightMap(op.shape, right.time, right.real_scale, right.imag_scale)
        grid = np.arange(system.nsize)
        probe = np.sin(grid*.37)
        assert np.array_equal(right.apply(probe), restored.apply(probe))
        assert np.array_equal(right.transpose(probe), restored.transpose(probe))
        np.savez_compressed(a.out/'right.npz', time=right.time,
            real_scale=right.real_scale, imag_scale=right.imag_scale)
        for case in old['solves']:
            path = a.known/case['file']
            assert sha(path) == case['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as z:
                target, truth = z['target'], z['dense_solution']
            for start in ('zero', 'nonzero'):
                x0 = np.zeros(system.nsize) if start == 'zero' else .3*truth+.02*probe
                initial = complex_array(x0, op.shape)*cap['scale'][None]
                nodes, info = refine(system, restored, target, initial)
                x = real_vector(nodes/cap['scale'][None])
                error = float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth), 1e-24))
                assert info['converged'] and error < 2e-7
                name = case['name']+'_'+start
                out = a.out/(name+'.npz')
                np.savez_compressed(out, target=target, initial_nodes=initial, nodes=nodes,
                    solution=x, dense_solution=truth, initial_solution=x0)
                r['cases'].append(dict(name=name, file=out.name, sha256=sha(out),
                    relative_dense_solution_error=error, **info))
                print('KNOWN correction', name, error, flush=True)
        r.update(result='observer_inverse_refinement_known_ready', controls=6,
            dense_sha256=sha(a.out/'dense_system.npz'), right_sha256=sha(a.out/'right.npz'))
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error));save(a.out/'report.json', r);raise


if __name__ == '__main__':
    main()
