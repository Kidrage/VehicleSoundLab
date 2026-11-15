"""Independent explicit dense audit of correction solves and saved right map."""
import argparse, os, shutil, sys
from pathlib import Path
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
    from observer_forward_v1.audit_oracle import synthesize, observe
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    shutil.copy2(repo/'tools/observer_forward_v1/audit_oracle.py', a.out/'executed_oracle.py')
    r = dict(result='running', cases=[], material_read=False)
    try:
        study = load(a.study/'report.json')
        assert study['result'] == 'observer_inverse_refinement_known_ready' and len(study['cases']) == 6
        for name, digest in study['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in study['inputs'].items():
            assert sha(name) == digest
        assert sha(a.study/'dense_system.npz') == study['dense_sha256']
        with np.load(a.study/'dense_system.npz') as z:
            c = {k:z[k] for k in z.files}
        positions, orders, scale = c['positions'], c['orders'], c['scale']
        shape = (len(positions), len(orders), 2)
        size = int(np.prod(shape))
        columns = []
        for j in range(2*size):
            x = np.zeros(2*size);x[j] = 1
            nodes = (x[:size]+1j*x[size:]).reshape(shape)*scale[None]
            y = observe(synthesize(nodes, positions, orders, int(c['frames'])), orders)/scale[None]
            columns.append(np.r_[y.real.ravel(), y.imag.ravel()])
        F = np.array(columns).T
        D = np.zeros((len(positions)-2, len(positions)))
        for j in range(len(D)):
            left, right = np.diff(positions[j:j+3])
            D[j, j:j+3] = [2*256**2/(left+right)/left,
                -2*256**2/(left+right)*(1/left+1/right), 2*256**2/(left+right)/right]
        dk = np.kron(D, np.eye(len(orders)*2))
        dr = np.zeros((2*len(dk), 2*size))
        dr[:len(dk), :size] = dk;dr[len(dk):, size:] = dk
        A = np.vstack([F, np.sqrt(.001)*dr, np.sqrt(.000001)*np.eye(2*size)])
        assert abs(A-c['matrix']).max() < 2e-12
        assert sha(a.study/'right.npz') == study['right_sha256']
        with np.load(a.study/'right.npz') as z:
            T, sr, si = z['time'], z['real_scale'], z['imag_scale']
        K = .001*D.T@D+.000001*np.eye(len(positions))
        assert abs(T.T@K@T-np.eye(len(T))).max() < 2e-9
        P = np.zeros((2*size, 2*size))
        for i in range(2*size):
            basis = np.zeros(2*size);basis[i] = 1
            u = (basis[:size]+1j*basis[size:]).reshape(shape)
            q = (T@(u.real*sr+1j*u.imag*si).reshape(len(T), -1)).reshape(shape)
            P[:, i] = np.r_[q.real.ravel(), q.imag.ravel()]
        assert np.linalg.matrix_rank(P) == len(P)
        for desc in study['cases']:
            path = a.study/desc['file'];assert sha(path) == desc['sha256']
            with np.load(path) as z:
                y = z['target']/scale[None]
                b = np.r_[y.real.ravel(), y.imag.ravel(), np.zeros(len(A)-2*y.size)]
                truth = np.linalg.lstsq(A, b, rcond=None)[0]
                x0, x = z['initial_solution'], z['solution']
                correction = np.linalg.lstsq(A@P, b-A@x0, rcond=None)[0]
                assert np.linalg.norm(x0+P@correction-truth)/max(np.linalg.norm(truth),1e-24) < 2e-7
                error = float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth), 1e-24))
                assert error < 2e-7
                residual = A@x-b
                objective = float(residual@residual)
                stationarity = float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b), 1e-24))
                assert abs(objective-desc['objective']) < 2e-9*max(1, objective)
                assert abs(stationarity-desc['relative_stationarity']) < 2e-10 and stationarity < 2e-7
                assert abs(float(np.linalg.norm(A@x0-b)**2)-desc['initial_objective']) < 2e-9*max(1, desc['initial_objective'])
                r['cases'].append(dict(name=desc['name'], relative_solution_error=error, relative_stationarity=stationarity))
        r.update(result='independent_observer_inverse_refinement_known_passed',
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__))
        save(a.out/'report.json', r);print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error));save(a.out/'report.json', r);raise


if __name__ == '__main__':
    main()
