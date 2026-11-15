"""Independent direct-wave bases qualify per-order data-aware right maps."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'): p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_frequency_v1.audit_oracle import matrices, metric
    from observer_complete_v1.audit_oracle import hats, curvature
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_frequency_v1/audit_oracle.py', 'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers): shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], stereo_verified=False, material_read=False)
    try:
        record = load(a.study/'report.json'); assert record['result'] == 'observer_frequency_block_known_ready'
        for name, digest in record['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        def direct_blocks(audio, positions, orders, scale, weights):
            M = len(positions); basis = hats(positions, len(audio)); D = curvature(positions)
            R = linalg.block_diag(.001*D.T@D+.000001*np.eye(M), .001*D.T@D+.000001*np.eye(M))
            result = []
            for h, order in enumerate(orders):
                phase = 2*np.pi*order*np.arange(len(audio))/1024
                B = np.column_stack((basis.T*np.cos(phase)[:, None], -basis.T*np.sin(phase)[:, None]))
                K = R+(scale[h, 0]*weights[4*order])**2*(B.T@B)
                T = linalg.solve_triangular(np.linalg.cholesky(K).T, np.eye(2*M), lower=False)
                assert np.max(abs(T.T@K@T-np.eye(2*M))) < 2e-8
                result.append(T)
            return np.array(result)
        for case in record['cases']:
            path = a.study/case['file']; assert sha(path) == case['sha256']
            with np.load(path) as z:
                _, _, weights, _, _ = metric(z['audio'], 64.)
                systems, Phi, D = matrices(z['positions'], z['orders'], z['scale'], z['audio'], weights, np.sqrt(np.mean(z['audio']**2)))
                A, b = systems['weighted_frame']
                blocks = direct_blocks(z['audio'], z['positions'], z['orders'], z['scale'], weights)
                assert np.max(abs(blocks-z['right_matrix'])) < 2e-8*max(1, abs(blocks).max())
                M, H = len(z['positions']), len(z['orders']); size = M*H; P = np.zeros((2*size, 2*size))
                for h in range(H):
                    ids = np.r_[np.arange(M)*H+h, size+np.arange(M)*H+h]
                    P[np.ix_(ids, ids)] = blocks[h]
                assert np.max(abs(P-z['P'])) < 2e-8*max(1, abs(P).max())
                exact = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                assert np.linalg.norm(z['solution']-exact)/np.linalg.norm(exact) < 2e-7
                g = np.linalg.norm(A.T@(A@z['solution']-b))/np.linalg.norm(A.T@b)
                assert g < 2e-7 and abs(g-case['relative_stationarity']) < 2e-9
                condition = float(np.linalg.cond(A@P))
                assert abs(condition-case['block_condition']) < 2e-7*condition
                assert np.linalg.matrix_rank(A) == len(exact) and np.linalg.svd(P, compute_uv=False).min() > 0
                r['cases'].append(dict(label=case['label'], block_condition=condition, relative_stationarity=float(g)))
        path = a.study/'stereo_map.npz'; assert sha(path) == record['stereo_map_sha256']
        with np.load(path) as z:
            _, _, weights, _, _ = metric(z['audio'], 64.)
            blocks = direct_blocks(z['audio'], z['positions'], z['orders'], z['scale'], weights)
            M, H, C = len(z['positions']), len(z['orders']), 2
            for key, output, transpose in (('u', 'forward', False), ('v', 'backward', True)):
                size = M*H*C; wave = z[key]; result = np.zeros_like(wave)
                for h in range(H):
                    for c in range(C):
                        ids = np.r_[(np.arange(M)*H+h)*C+c, size+(np.arange(M)*H+h)*C+c]
                        block = blocks[h].T if transpose else blocks[h]
                        result[ids] = block@wave[ids]
                assert np.max(abs(result-z[output])) < 2e-8*max(1, abs(result).max())
        r.update(result='independent_observer_frequency_block_known_passed', stereo_verified=True,
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo/n) for n in helpers})
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
