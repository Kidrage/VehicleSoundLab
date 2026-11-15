"""Small explicit estimator controls; no source fitting or solver stopping claims."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from krylov_diagnostic_v1.stable_residual import estimate
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, material_read=False)
    try:
        for name in ('tools/run_observer_stable_controls_v1.py', 'tools/krylov_diagnostic_v1/stable_residual.py',
                'research/observer_stable_residual_v1_plan.json'):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        fixtures = []
        for label, A, b, count in (
                ('rectangular', np.array([[2., 0.], [1., 3.], [0., 1.], [0., 0.]]), np.array([1., 2., 3., .125]), 2),
                ('outside_gradient', np.array([[2., 1.], [0., 3.], [0., 0.]]), np.array([1., 1., 1.]), 1),
                ('cancellation', np.array([[2.**36, 0.], [0., 2.**16], [1., 1.], [0., 0.]]), np.array([2.**36+.25, 2.**16+.1, 2., .001]), 2),
                ('ill_conditioned', np.array([[1e8, 1e8], [0., 2.], [1., 0.], [0., 1.]]), np.array([1e8, 2., .2, .3]), 2),
                ('exact_square', np.array([[2., 1.], [0., 4.]]), np.array([1., 3.]), 2),
                ('zero_rhs', np.array([[2., 0.], [0., 3.], [0., 0.]]), np.zeros(3), 2)):
            V = np.eye(A.shape[1])[:, :count]
            if not np.linalg.norm(b):
                U = np.eye(len(b))
            elif len(b) == count:
                U = linalg.qr(np.column_stack((b, np.eye(len(b))[:, 1:])), mode='economic')[0]
                if U[:, 0]@b < 0:
                    U[:, 0] *= -1
            else:
                raw = np.column_stack((b/np.linalg.norm(b), A@V))
                U = linalg.qr(raw, mode='economic')[0]
                if U[:, 0]@b < 0:
                    U[:, 0] *= -1
            H = U.T@A@V
            fixtures.append((label, A, b, U, V, H))
        # A projected residual can vanish while the actual full gradient is nonzero.
        # Deliberately perturbed projection, retained to exercise the discrepancy guard.
        A = np.array([[2., 0.], [0., 3.], [1., 1.]])
        b = np.array([1., 2., 3.])
        U = linalg.qr(np.column_stack((b, np.eye(3)[:, :2])))[0]
        if U[:, 0]@b < 0:
            U[:, 0] *= -1
        V = np.eye(2)
        fixtures.append(('projection_defect', A, b, U, V, (U.T@A)*1.01))
        for label, A, b, U, V, H in fixtures:
            capture, info = estimate(H, U, V, b, lambda x:A.T@x, lambda x:A@x)
            capture.update(A=A, rhs=b, U=U, V=V, H=H)
            dest = a.out/(label+'.npz')
            np.savez_compressed(dest, **capture)
            r['cases'].append(dict(label=label, file=dest.name, sha256=sha(dest), info=info))
            save(a.out/'report.json', r)
            print(label, info, flush=True)
        r.update(result='observer_stable_controls_measured', source_or_full_solver_qualified=False)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
