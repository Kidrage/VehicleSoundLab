"""Explicit known controls before the one short full288 orthogonality probe."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.sparse.linalg import aslinearoperator
    from krylov_diagnostic_v1.bidiagonal import probe
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[], material_read=False)
    try:
        names = ('tools/run_observer_krylov_known_v1.py',
            'tools/krylov_diagnostic_v1/bidiagonal.py', 'research/observer_representer_krylov_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        controls = []
        def rhs(m):
            return np.sin(np.arange(m)*.723+.1)+.3*np.cos(np.arange(m)*.23)
        for tag, A, b, steps in (
                ('zero_rhs', np.eye(5), np.zeros(5), 8),
                ('zero_operator', np.zeros((7, 5)), rhs(7), 8),
                ('negative_identity', -3*np.eye(8), rhs(8), 16),
                ('rank_one', np.outer(np.arange(1., 10), np.arange(1., 7)), np.arange(1., 10), 16),
                ('diagonal', np.diag(np.geomspace(.1, 20., 24)), rhs(24), 48),
                ('clustered', np.diag(1+np.arange(32)*1e-8), rhs(32), 64),
                ('ill_conditioned', np.diag(np.geomspace(1e-8, 1e8, 40)), rhs(40), 64)):
            controls.append((tag, A, b, steps, {}))
        old = load(a.original/'report.json')
        assert old['result'] == 'observer_representer_primal_algebra_measured' and old['all_qualified']
        r['inputs'][str(a.original/'report.json')] = sha(a.original/'report.json')
        for row in old['cases']:
            path = a.original/row['file']
            assert sha(path) == row['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as z:
                B, T = z['B'], z['T']
                A = np.vstack((B@T, np.eye(T.shape[0])))
                b = np.r_[z['b'][:len(B)], np.zeros(T.shape[0])]
            controls.append(('algebra_'+row['label'], A, b, 64, dict(original_file=str(path))))
        for tag, A, b, steps, extra in controls:
            capture, info = probe(aslinearoperator(A), b, steps)
            capture['A'] = A
            dest = a.out/(tag+'.npz')
            np.savez_compressed(dest, **capture)
            r['cases'].append(dict(label=tag, file=dest.name, sha256=sha(dest), info=info, **extra))
            save(a.out/'report.json', r)
            print(tag, info['status'], info['forward_steps'], info['U_max_offdiagonal'], info['V_max_offdiagonal'], flush=True)
        r.update(result='observer_krylov_known_measured', full_probe_or_source_fit=False)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
