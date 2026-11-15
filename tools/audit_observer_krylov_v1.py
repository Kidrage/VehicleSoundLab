"""Independent recurrence, sign, breakdown and Gram checks; no diagnostic import."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--original', type=Path)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], maximum_errors={}, oracles_sha256={})
    def check(name, x, y, scale=1., gate=2e-10):
        x, y = np.asarray(x), np.asarray(y)
        error = float(np.max(abs(x-y))/scale) if x.size else 0.
        assert x.shape == y.shape and error < gate, (name, error, x.shape, y.shape)
        r['maximum_errors'][name] = error
    def gram(x):
        # Independent block reduction instead of the producer's single GEMM.
        out = np.zeros((x.shape[1], x.shape[1]))
        for j in range(0, len(x), 4096):
            out += x[j:j+4096].T@x[j:j+4096]
        return out
    def inspect(label, z, info, forward, backward):
        U, V, alpha, beta, rhs = (z[n] for n in ('U', 'V', 'alpha', 'beta', 'rhs'))
        assert all(np.isfinite(v).all() for v in (U, V, alpha, beta, rhs))
        assert np.all(alpha >= 0) and np.all(beta >= 0)
        assert U.shape[1] == info['U_columns'] and V.shape[1] == info['V_columns']
        assert len(alpha) == info['adjoint_steps'] and len(beta) == info['forward_steps']
        assert info['near_breakdown_relative_threshold'] == 64*np.finfo(float).eps
        check(label+'_beta0', np.linalg.norm(rhs), info['beta0'])
        if len(U.T):
            check(label+'_first_U', U[:, 0], rhs/np.linalg.norm(rhs))
        gu, gv = gram(U), gram(V)
        check(label+'_U_gram', gu, z['U_gram'])
        check(label+'_V_gram', gv, z['V_gram'])
        for tag, g in (('U', gu), ('V', gv)):
            d = np.diag(g)
            off = abs(g-np.diag(d))
            maximum = float(off.max()) if g.size else 0.
            diagonal = float(np.max(abs(d-1))) if d.size else 0.
            check(label+'_'+tag+'_max_offdiagonal', maximum, info[tag+'_max_offdiagonal'])
            check(label+'_'+tag+'_max_diagonal_error', diagonal, info[tag+'_max_diagonal_error'])
            assert diagonal < 2e-12
        forward_errors, adjoint_errors = [], []
        for j, b in enumerate(beta):
            raw = forward(V[:, j])
            residual = raw-alpha[j]*U[:, j]
            reconstructed = b*U[:, j+1] if j+1 < U.shape[1] else np.zeros_like(raw)
            denominator = max(float(np.linalg.norm(raw))+alpha[j], 1e-300)
            error = float(np.linalg.norm(residual-reconstructed)/denominator)
            normerror = abs(float(np.linalg.norm(residual))-b)/denominator
            assert max(error, normerror) < 2e-10, (label, 'forward', j, error, normerror)
            forward_errors.append(max(error, normerror))
            if j+1 == U.shape[1]:
                assert b <= 2*info['near_breakdown_relative_threshold']*denominator
        for j, v in enumerate(alpha):
            raw = backward(U[:, j])
            previous = beta[j-1]*V[:, j-1] if j else np.zeros_like(raw)
            residual = raw-previous
            reconstructed = v*V[:, j] if j < V.shape[1] else np.zeros_like(raw)
            denominator = max(float(np.linalg.norm(raw))+(beta[j-1] if j else 0.), 1e-300)
            error = float(np.linalg.norm(residual-reconstructed)/denominator)
            normerror = abs(float(np.linalg.norm(residual))-v)/denominator
            assert max(error, normerror) < 2e-10, (label, 'adjoint', j, error, normerror)
            adjoint_errors.append(max(error, normerror))
            if j == V.shape[1]:
                assert v <= 2*info['near_breakdown_relative_threshold']*denominator
        def first(g):
            for j in range(1, len(g)):
                if np.max(abs(g[j, :j])) > 1e-8:
                    return j
            return None
        row = dict(label=label, U_max_offdiagonal=info['U_max_offdiagonal'],
            V_max_offdiagonal=info['V_max_offdiagonal'], U_first_column_above_1e_minus8=first(gu),
            V_first_column_above_1e_minus8=first(gv),
            max_forward_recurrence_error=max(forward_errors, default=0.),
            max_adjoint_recurrence_error=max(adjoint_errors, default=0.),
            status=info['status'], forward_steps=len(beta), adjoint_steps=len(alpha))
        r['cases'].append(row)
        print(label, row, flush=True)
    try:
        source = load(a.study/'report.json')
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in source.get('inputs', {}).items():
            assert sha(name) == digest
        if source['result'] == 'observer_krylov_known_measured':
            def rhs(m):
                n = np.arange(m)
                return np.sin(.723*n+.1)+.3*np.cos(.23*n)
            explicit = {
                'zero_rhs':(np.eye(5), np.zeros(5)),
                'zero_operator':(np.zeros((7, 5)), rhs(7)),
                'negative_identity':(-3*np.eye(8), rhs(8)),
                'rank_one':(np.arange(1., 10)[:, None]*np.arange(1., 7), np.arange(1., 10)),
                'diagonal':(np.diag(np.geomspace(.1, 20., 24)), rhs(24)),
                'clustered':(np.diag(1+1e-8*np.arange(32)), rhs(32)),
                'ill_conditioned':(np.diag(np.geomspace(1e-8, 1e8, 40)), rhs(40))}
            assert len(source['cases']) == 11
            for row in source['cases']:
                path = a.study/row['file']
                assert sha(path) == row['sha256']
                with np.load(path) as z:
                    if row['label'] in explicit:
                        A, b = explicit[row['label']]
                    else:
                        with np.load(row['original_file']) as old:
                            T = np.linalg.solve(np.linalg.cholesky(old['R']).T, np.eye(len(old['R'])))
                            A = np.concatenate((old['B']@T, np.eye(len(T))), axis=0)
                            b = np.r_[old['b'][:len(old['B'])], np.zeros(len(T))]
                    check(row['label']+'_matrix', A, z['A'], max(1., abs(A).max()))
                    check(row['label']+'_rhs', b, z['rhs'])
                    inspect(row['label'], z, row['info'], lambda x:A@x, lambda x:A.T@x)
                expected = {'zero_rhs':'zero_rhs', 'zero_operator':'adjoint_near_breakdown',
                    'negative_identity':'forward_near_breakdown', 'rank_one':'forward_near_breakdown'}
                if row['label'] in expected:
                    assert row['info']['status'] == expected[row['label']]
                    assert row['info']['forward_steps'] <= 1
            r['result'] = 'independent_observer_krylov_known_passed'
        else:
            assert source['result'] == 'observer_krylov_full_diagnostic_measured'
            assert a.original and source['only_one_fixed128_probe']
            for name, digest in source['files'].items():
                assert sha(a.study/name) == digest
            from scipy import linalg
            from observer_supported_v1.full_oracle import FullOracle, vec
            helpers = ('tools/observer_supported_v1/full_oracle.py', 'tools/observer_supported_v1/audit_oracle.py',
                'tools/observer_frequency_v1/reduced_oracle.py', 'tools/observer_frequency_v1/audit_oracle.py',
                'tools/observer_complete_v1/audit_oracle.py')
            for j, name in enumerate(helpers):
                shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
                r['oracles_sha256'][name] = sha(repo/name)
            original = load(a.original/'report.json')
            assert sha(a.original/'capture.npz') == original['capture_sha256']
            with np.load(a.original/'capture.npz') as z:
                oracle = FullOracle(z['audio'], z['positions'], z['orders'], z['scale'])
            L = np.linalg.cholesky(oracle.R)
            def root(x, transpose):
                q = oracle.nodes(x)
                return vec(linalg.solve_triangular(L if transpose else L.T, q.reshape(len(q), -1),
                    lower=transpose).reshape(q.shape))
            def forward(x):
                return np.r_[oracle.data_forward(root(x, False)), x]
            def backward(y):
                return root(oracle.data_adjoint(y[:oracle.data_size]), True)+y[oracle.data_size:]
            with np.load(a.study/'coefficients.npz') as c:
                z = {n:c[n] for n in c.files}
            z.update(U=np.load(a.study/'basis_U.npy', mmap_mode='r'), V=np.load(a.study/'basis_V.npy', mmap_mode='r'))
            check('full_rhs', z['rhs'], np.r_[oracle.target(), np.zeros(z['V'].shape[0])], max(abs(z['rhs']).max(), 1.))
            assert source['info']['requested_steps'] == source['info']['forward_steps'] == 128
            inspect('full128', z, source['info'], forward, backward)
            r.update(result='independent_observer_krylov_full_passed',
                all128_forward_and_adjoint_recurrences_verified=True,
                orthogonality_loss_not_sole_convergence_or_timbre_cause=True,
                no_solution_or_material_or_runtime_qualification=True)
        r.update(producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__))
        save(a.out/'report.json', r)
        print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
