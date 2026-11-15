"""Independent SVD-complement and explicit full-gradient audit of stable QR solves."""
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
    from scipy import linalg
    from observer_supported_v1.audit_oracle import metric, matrices
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_supported_v1/audit_oracle.py', 'tools/observer_frequency_v1/reduced_oracle.py',
        'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers):
        shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], maximum_errors={})
    def check(name, x, y, scale=1., gate=2e-8):
        x, y = np.asarray(x), np.asarray(y)
        error = float(np.max(abs(x-y))/scale) if x.size else 0.
        assert x.shape == y.shape and error < gate, (name, error)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    def vec(q):
        return np.r_[q.real.ravel(), q.imag.ravel()]
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'observer_stable_known_measured' and len(source['cases']) == 12
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for case in source['cases']:
            path = a.study/case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z, np.load(case['original_file']) as old:
                scale = z['scale']
                if case['kind'] == 'Hann':
                    A, b, Phi, R, rows = matrices(old['positions'], old['orders'], scale, old['audio'])
                    original = vec(old['original_dense_nodes']/scale[None])
                else:
                    C, N, M, H = old['audio'].shape[1], 33, 9, 3
                    size = M*H*C
                    Phi = np.zeros((N*C, 2*size))
                    for m in range(M):
                        hat = np.maximum(1-abs(np.arange(N)-4*m)/4, 0.)
                        for h, order in enumerate((7, 8, 211)):
                            angle = 2*np.pi*((np.arange(N)*order) % 1024)/1024
                            for c in range(C):
                                j = (m*H+h)*C+c
                                Phi[c::C, j] = hat*np.cos(angle)*scale[h, 0]
                                Phi[c::C, size+j] = -hat*np.sin(angle)*scale[h, 0]
                    dct = np.sqrt(2/N)*np.cos(np.pi*np.arange(N)[:, None]*(np.arange(N)[None, :]+.5)/N)
                    dct[0] /= np.sqrt(2.)
                    W = np.kron(np.eye(N)+dct.T@(np.geomspace(1., 100., N)[:, None]**2*dct), np.eye(C))
                    check('algebra_original_Phi', Phi, old['Phi'])
                    check('algebra_original_W', W, old['H'], max(abs(W).max(), 1.))
                    D = np.zeros((7, 9))
                    for j in range(7):
                        D[j, j:j+3] = [1., -2., 1.]
                    K = .001*D.T@D+1e-6*np.eye(9)
                    R = linalg.block_diag(np.kron(K, np.eye(H*C)), np.kron(K, np.eye(H*C)))
                    A, b, rows, original = old['A'], old['b'], len(Phi), old['original']
                    check('algebra_original_R', R, old['R'])
                    check('algebra_original_B_metric', A[:rows].T@A[:rows], Phi.T@W@Phi, max(abs(Phi.T@W@Phi).max(), 1.))
                    check('algebra_original_regularizer', A[rows:].T@A[rows:], R)
                B, target = A[:rows], b[:rows]
                T = linalg.solve_triangular(np.linalg.cholesky(R).T, np.eye(len(R)), lower=False)
                G = np.vstack((B@T, np.eye(len(R))))
                rhs = np.r_[target, np.zeros(len(R))]
                check('square_root_rhs', rhs, z['rhs'])
                U, V, Hproj = z['U'], z['V'], z['H']
                check('left_basis_orthogonal', U.T@U, np.eye(U.shape[1]), gate=2e-12)
                check('right_basis_orthogonal', V.T@V, np.eye(V.shape[1]), gate=2e-12)
                check('left_basis_Gram', U.T@U, z['U_gram'])
                check('right_basis_Gram', V.T@V, z['V_gram'])
                check('projected_operator', G@V, U@Hproj, max(1., np.linalg.norm(G)))
                small_b = np.zeros(len(Hproj))
                small_b[0] = np.linalg.norm(rhs)
                y = linalg.lstsq(Hproj, small_b, lapack_driver='gelsd')[0]
                check('projected_QR_solution', y, z['y'], max(1., abs(y).max()))
                check('solution_in_basis', V@z['y'], z['z'])
                x = vec(z['fitted']/scale[None])
                check('restore_from_root', T@z['z'], x)
                exact = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                check('saved_original_dense', exact, original)
                relative = float(np.linalg.norm(x-original)/np.linalg.norm(original))
                check('dense_relative_error', relative, case['dense_relative_error'])
                e, residual = A@x-b, B@x-target
                gradient = float(np.linalg.norm(A.T@e)/np.linalg.norm(A.T@b))
                check('original_gradient', gradient, case['solver']['relative_stationarity'])
                primal = float(e@e)
                check('original_objective', primal, case['solver']['objective'])
                certificates = {}
                for kind in ('residual', 'representer'):
                    cert = case[kind+'_certificate']
                    if kind == 'residual':
                        t = cert['residual_dual_scale']
                        v = linalg.solve(R, B.T@residual, assume_a='pos')
                        gap = float((1-t)**2*(residual@residual)+(x+t*v)@R@(x+t*v))
                    else:
                        u = z['u']
                        v = linalg.solve(R, B.T@u, assume_a='pos')
                        gap = float((residual+u)@(residual+u)+(x-v)@R@(x-v))
                    check(kind+'_gap', gap, cert['gap_upper_bound'])
                    passed = bool(gap <= 1e-6*primal+1e-10)
                    assert passed == cert['additional_gap_gate_passed']
                    certificates[kind] = dict(gap=gap, passed=passed)
                s = case['solver']
                assert not s['scipy_LSMR'] and s['atol'] == s['btol'] == 1e-11 and s['maxiter'] == 4000
                assert s['conlim'] == 1e12 and s['full_adjoint_includes_outside_subspace']
                # SVD complement is independent of the producer's complete QR.
                complement = linalg.null_space(Hproj.T)
                assert complement.shape[1] == Hproj.shape[0]-Hproj.shape[1]
                coefficients = -complement@(complement.T@small_b)
                check('stable_coefficients', coefficients, z['residual_coefficients'], max(1., np.linalg.norm(rhs)))
                stable = U@coefficients
                normal = G.T@stable
                check('stable_residual', stable, z['stable_residual'], max(1., np.linalg.norm(rhs)))
                check('stable_full_normal', normal, z['stable_normal'], max(1., np.linalg.norm(G)*np.linalg.norm(rhs)))
                outside = normal-V@(V.T@normal)
                check('outside_normal', outside, z['outside_normal'], max(1., np.linalg.norm(G)*np.linalg.norm(rhs)))
                nr = float(np.linalg.norm(coefficients))
                normal_relative = float(np.linalg.norm(normal)/max(np.linalg.norm(Hproj)*nr, 1e-300))
                independent_direct = G@z['z']-rhs
                independent_backward = float(np.linalg.norm(independent_direct-stable)/np.linalg.norm(rhs))
                # Exact execution arithmetic is captured; independent dense products
                # additionally check the same backward-error guard, not just its flag.
                saved_backward = float(np.linalg.norm(z['direct_residual']-z['stable_residual'])/np.linalg.norm(rhs))
                check('saved_backward', saved_backward, s['relative_backward_discrepancy'])
                assert saved_backward <= 1e-11 and independent_backward <= 1e-11
                assert normal_relative <= 1e-11
                assert s['accepted'] and s['backward_discrepancy_guard_passed'] and s['original_checks_mandatory']
                assert all(s['original_checks'][name] for name in ('qualified', 'residual_gap_passed', 'representer_gap_passed'))
                normz = float(np.linalg.norm(z['z']))
                stop = (1 if s['stable_residual_norm'] <= 1e-11*np.linalg.norm(rhs)+1e-11*s['projected_Frobenius_estimate']*normz
                    else 2 if s['stable_normal_relative'] <= 1e-11 else 3 if s['projected_condition'] >= 1e12 else 7)
                assert stop == s['stop'] and stop in (1, 2)
                transformed_residual = independent_direct
                normal = float(np.linalg.norm(G.T@transformed_residual))
                exact_z = linalg.solve_triangular(T, exact, lower=False)
                exact_r = G@exact_z-rhs
                exact_normal_relative = float(np.linalg.norm(G.T@exact_r)/(np.linalg.norm(G)*np.linalg.norm(exact_r)))
                qualified = bool(relative < 2e-7 and gradient < 2e-7 and stop in (1, 2, 4, 5)
                    and all(c['passed'] for c in certificates.values()))
                assert qualified == case['qualified']
                r['cases'].append(dict(kind=case['kind'], label=case['label'], qualified=qualified,
                    dense_relative_error=relative, gradient=gradient, original_objective=primal,
                    certificates=certificates, stopping_code=stop,
                    independent_direct_transformed_normal_relative=normal/(np.linalg.norm(G)*np.linalg.norm(transformed_residual)),
                    independent_original_dense_transformed_normal_relative=exact_normal_relative,
                    stable_normal_relative=normal_relative, independent_backward_discrepancy=independent_backward,
                    max_U_offdiagonal=float(np.max(abs(U.T@U-np.eye(U.shape[1])))),
                    max_V_offdiagonal=float(np.max(abs(V.T@V-np.eye(V.shape[1]))))))
                print('AUDITED STABLE', case['kind'], case['label'], qualified, 'stop', stop, 'dense-normal', exact_normal_relative, flush=True)
        r.update(result='independent_observer_stable_known_passed', all_qualified=all(c['qualified'] for c in r['cases']),
            pass_count=sum(c['qualified'] for c in r['cases']), original_gates_not_relaxed=True,
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
