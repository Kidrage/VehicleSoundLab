"""Independent explicit original-Hann matrices and both feasible-dual certificates."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'original', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import metric, matrices
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    helpers = ('tools/observer_supported_v1/audit_oracle.py', 'tools/observer_frequency_v1/reduced_oracle.py',
        'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers):
        shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], maximum_errors={})
    def check(name, x, y, scale=1., gate=2e-8):
        x, y = np.asarray(x), np.asarray(y)
        error = float(np.max(abs(x-y))/scale)
        assert x.shape == y.shape and error < gate, (name, error)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    def vec(q):
        return np.r_[q.real.ravel(), q.imag.ravel()]
    try:
        source, old = load(a.study/'report.json'), load(a.original/'report.json')
        assert source['result'] == 'observer_representer_context_measured'
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in source['inputs'].items():
            assert sha(name) == digest
        for case, original in zip(source['cases'], old['cases']):
            assert case['label'] == original['label']
            path = a.study/case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z, np.load(a.original/original['file']) as o:
                for name in ('audio', 'positions', 'orders', 'scale', 'source_nodes'):
                    assert np.array_equal(z[name], o[name])
                assert np.array_equal(z['original_dense_nodes'], o['dense_nodes'])
                m = metric(z['audio'], 64.)
                A, b, Phi, R, data_rows = matrices(z['positions'], z['orders'], z['scale'], z['audio'], m)
                exact = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                x = vec(z['fitted']/z['scale'][None])
                relative = float(np.linalg.norm(x-exact)/np.linalg.norm(exact))
                check('dense_relative_error', relative, case['dense_relative_error'])
                e = A@x-b
                grad = float(np.linalg.norm(A.T@e)/np.linalg.norm(A.T@b))
                check('original_gradient', grad, case['solver']['relative_stationarity'])
                B, y = A[:data_rows], b[:data_rows]
                residual = B@x-y
                certs = {}
                for tag in ('residual', 'representer'):
                    cert = case[tag+'_certificate']
                    if tag == 'residual':
                        t = cert['residual_dual_scale']
                        v = linalg.solve(R, B.T@residual, assume_a='pos')
                        gap = float((1-t)**2*(residual@residual)+(x+t*v)@R@(x+t*v))
                        lower = float(-t*t*(residual@residual+(B.T@residual)@v)-2*t*(y@residual))
                    else:
                        u = z['u']
                        assert u.shape == y.shape
                        v = linalg.solve(R, B.T@u, assume_a='pos')
                        gap = float((residual+u)@(residual+u)+(x-v)@R@(x-v))
                        lower = float(2*y@u-u@u-v@R@v)
                    primal = float(e@e)
                    for name, value in dict(primal=primal, dual_lower_bound=lower, gap_upper_bound=gap).items():
                        check(tag+'_'+name, value, cert[name], max(1., abs(value)))
                    passed = bool(gap <= 1e-6*primal+1e-10)
                    assert passed == cert['additional_gap_gate_passed']
                    certs[tag] = dict(gap=gap, passed=passed)
                truth = vec(z['source_nodes']/z['scale'][None])
                high_ids = np.r_[np.arange(17)*2+1, 34+np.arange(17)*2+1]
                high_truth = Phi[:, high_ids]@truth[high_ids]
                high_error = Phi[:, high_ids]@(x-truth)[high_ids]
                diff = Phi@x-z['audio'].ravel()
                crop = slice(2176, 6529)
                stats = dict(whole_wave_NRMSE=float(np.linalg.norm(diff)/np.linalg.norm(z['audio'])),
                    target_wave_NRMSE=float(np.linalg.norm(diff[crop])/np.linalg.norm(z['audio'][crop])),
                    whole_high_NRMSE=float(np.linalg.norm(high_error)/np.linalg.norm(high_truth)),
                    target_high_NRMSE=float(np.linalg.norm(high_error[crop])/np.linalg.norm(high_truth[crop])))
                for name, value in stats.items():
                    check(name, value, case['metrics'][name])
                qualified = bool(relative < 2e-7 and grad < 2e-7 and case['solver']['stop'] in (1, 2, 4, 5)
                    and all(c['passed'] for c in certs.values()))
                assert qualified == case['qualified']
                r['cases'].append(dict(label=case['label'], qualified=qualified, dense_relative_error=relative,
                    gradient=grad, certificates=certs, metrics=stats))
                print('AUDITED ORIGINAL METRIC', case['label'], qualified, flush=True)
        assert len(r['cases']) == 8
        assert r['cases'][-1]['metrics']['whole_high_NRMSE'] > .02
        r.update(result='independent_observer_representer_context_passed', all_qualified=all(c['qualified'] for c in r['cases']),
            original_outer_loss_preserved=True, producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__), oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json', r)
        print(r['result'], r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
