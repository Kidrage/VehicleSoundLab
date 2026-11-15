"""Independent finite matrix, representer and failed/successful solver gate audit."""
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
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], maximum_errors={})
    def check(name, x, y, scale=1., gate=2e-8):
        x, y = np.asarray(x), np.asarray(y)
        err = float(np.max(abs(x-y))/scale)
        assert x.shape == y.shape and err < gate, (name, err)
        r['maximum_errors'][name] = max(err, r['maximum_errors'].get(name, 0.))
    try:
        report = load(a.study/'report.json')
        assert report['result'] in ('observer_representer_algebra_measured', 'observer_representer_primal_algebra_measured')
        repo = Path(__file__).resolve().parents[1]
        for n, digest in report['sources'].items():
            assert sha(repo/n) == sha(a.study/'exact_sources'/n) == digest
        for case in report['cases']:
            path = a.study/case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z:
                C = case['channels']
                N, M, H = 33, 9, 3
                size = M*H*C
                Phi = np.zeros((N*C, 2*size))
                for m in range(M):
                    hat = np.maximum(1-abs(np.arange(N)-4*m)/4, 0.)
                    for h, order in enumerate((7, 8, 211)):
                        phase = 2*np.pi*((np.arange(N)*order) % 1024)/1024
                        for c in range(C):
                            j = (m*H+h)*C+c
                            Phi[c::C, j] = hat*np.cos(phase)*z['scale'][h, 0]
                            Phi[c::C, size+j] = -hat*np.sin(phase)*z['scale'][h, 0]
                dct = np.sqrt(2/N)*np.cos(np.pi*np.arange(N)[:, None]*(np.arange(N)[None, :]+.5)/N)
                dct[0] /= np.sqrt(2.)
                Hwave = np.kron(np.eye(N)+dct.T@(np.geomspace(1., 100., N)[:, None]**2*dct), np.eye(C))
                D = np.zeros((7, 9))
                for m in range(7):
                    D[m, m:m+3] = [1., -2., 1.]
                Rnode = .001*D.T@D+1e-6*np.eye(9)
                R = linalg.block_diag(np.kron(Rnode, np.eye(H*C)), np.kron(Rnode, np.eye(H*C)))
                check('Phi', Phi, z['Phi'])
                check('Hwave', Hwave, z['H'], max(1., abs(Hwave).max()))
                check('R', R, z['R'])
                L = np.linalg.cholesky(Hwave).T
                B = L@Phi
                check('data_matrix', B, z['B'], max(1., abs(B).max()))
                assert np.max(abs(z['T']@z['T'].T@R-np.eye(2*size))) < 2e-8
                check('original_data_metric', z['B'].T@z['B'], Phi.T@Hwave@Phi, max(1., abs(Phi.T@Hwave@Phi).max()))
                # Use saved Cholesky basis after independently verifying its metric;
                # Cholesky basis rotations need not be bit-identical under roundoff.
                data, A, b = z['B'], z['A'], z['b']
                check('original_normal_penalty', A.T@A-data.T@data, R, max(1., abs(R).max()))
                exact = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                check('original_SVD', exact, z['original'])
                null = z['null_basis']
                check('null_observation', Phi@null, np.zeros((N*C, null.shape[1])))
                check('null_orthogonal', null.T@null, np.eye(null.shape[1]))
                result = dict(label=case['label'], variants={})
                tags = [('original', 'original'), ('dense_dual', 'dense_dual'),
                        ('iterative', case.get('iterative_tag', 'iterative_dual'))]
                if 'plain' in z:
                    tags.append(('plain', 'plain_sample_normal'))
                for field, tag in tags:
                    q = z[field]
                    residual = A@q-b
                    stat = dict(dense_relative_error=float(np.linalg.norm(q-exact)/np.linalg.norm(exact)),
                        relative_stationarity=float(np.linalg.norm(A.T@residual)/np.linalg.norm(A.T@b)),
                        objective=float(residual@residual))
                    for key, value in stat.items():
                        check(tag+'_'+key, value, case['stats'][tag][key])
                    result['variants'][tag] = stat
                if 'probe' in z:
                    G = np.vstack(((data@z['T']).T, np.eye(N*C)))
                    check('dual_forward', G@z['probe'], z['forward'], max(1., abs(z['forward']).max()))
                    check('dual_adjoint', G.T@z['test'], z['backward'], max(1., abs(z['backward']).max()))
                else:
                    G = np.vstack((data@z['T'], np.eye(2*size)))
                    check('primal_forward', G@z['primal_probe'], z['primal_forward'], max(1., abs(z['primal_forward']).max()))
                    check('primal_adjoint', G.T@z['primal_test'], z['primal_backward'], max(1., abs(z['primal_backward']).max()))
                for tag, field, uf, prefix in (('dense', 'dense_dual', 'dense_u', 'dense_'),
                                              ('iterative', 'iterative', 'u', '')):
                    q = z[field]
                    e = data@q-b[:N*C]
                    for typ in ('residual', 'representer'):
                        cert = case[prefix+typ+'_certificate']
                        if typ == 'residual':
                            t = cert['residual_dual_scale']
                            v = linalg.solve(R, data.T@e, assume_a='pos')
                            gap = float((1-t)**2*(e@e)+(q+t*v)@R@(q+t*v))
                            dual_value = float(-t*t*(e@e+(data.T@e)@v)-2*t*(b[:N*C]@e))
                        else:
                            u = z[uf]
                            v = linalg.solve(R, data.T@u, assume_a='pos')
                            gap = float((e+u)@(e+u)+(q-v)@R@(q-v))
                            dual_value = float(2*b[:N*C]@u-u@u-v@R@v)
                        primal = float(e@e+q@R@q)
                        for key, value in dict(primal=primal, dual_lower_bound=dual_value, gap_upper_bound=gap).items():
                            check(tag+'_'+typ+'_'+key, value, cert[key])
                        assert bool(gap <= 1e-6*primal+1e-10) == cert['additional_gap_gate_passed']
                itag = case.get('iterative_tag', 'iterative_dual')
                s, d = result['variants'][itag], result['variants']['dense_dual']
                info = case['iterative_solve']
                qualified = bool(d['dense_relative_error'] < 2e-7 and d['relative_stationarity'] < 2e-7 and
                    s['dense_relative_error'] < 2e-7 and s['relative_stationarity'] < 2e-7 and info['stop'] in (1, 2, 4, 5)
                    and all(case[n]['additional_gap_gate_passed'] for n in ('residual_certificate', 'representer_certificate',
                        'dense_residual_certificate', 'dense_representer_certificate')))
                assert qualified == case['qualified']
                result['qualified'] = qualified
                result['dense_equivalence_qualified'] = bool(d['dense_relative_error'] < 2e-7 and d['relative_stationarity'] < 2e-7)
                r['cases'].append(result)
                print('AUDITED REPRESENTATION', case['label'], qualified, flush=True)
        assert len(r['cases']) == 4
        r.update(result='independent_observer_representer_algebra_passed',
            all_qualified=all(c['qualified'] for c in r['cases']),
            dense_equivalence_all_qualified=all(c['dense_equivalence_qualified'] for c in r['cases']),
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__))
        save(a.out/'report.json', r)
        print(r['result'], 'iterative', r['all_qualified'], 'dense', r['dense_equivalence_all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
