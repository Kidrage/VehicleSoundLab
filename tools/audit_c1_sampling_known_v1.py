"""Independent native analytic tones, complete FIR and every source query."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_source_prepare_v1.audit_sampling import verify
    from locked_source_tail_v1.audit_kernel import analytic
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    r = dict(result='running', producer_sha256=sha(a.study/'report.json'), inputs={}, cases=[], maximum_errors={})
    def check(name, actual, expected, gate=2e-12, scale=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        if scale is None: scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
        error = error/scale if scale else error
        if not scale: assert error == 0
        assert error <= gate, (name, error, gate)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
    try:
        info = load(a.study/'report.json'); assert info['result'] == 'c1_sampling_known_measured' and info['all_qualified']
        assert len(info['cases']) == 4 and len(info['invalid_rejections']) == 8 and not info['material_read']
        for name, expected in info['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for path, expected in info['inputs'].items(): assert sha(path) == expected; r['inputs'][path] = expected
        for row in info['cases']:
            path = a.study/row['file']; assert sha(path) == row['sha256']; r['inputs'][str(path)] = sha(path)
            with np.load(path) as f: z = {k:f[k] for k in f.files}
            freq = np.array([64., 3200., 14080., 19072., 21952., 23424.]); assert np.array_equal(z['frequencies'], freq)
            coef = np.empty((6, 2), complex)
            for i, f in enumerate(freq):
                coef[i, 0] = .13/(i+1)*complex(math.cos(.29*i), math.sin(.29*i))
                angle = 1.1+.81*i; coef[i, 1] = .0793/(i+1)*complex(math.cos(angle), math.sin(angle))
                if row['label'] == 'nonlinear_delay':
                    angle = -2*math.pi*f*.00035; coef[i, 1] = .63*coef[i, 0]*complex(math.cos(angle), math.sin(angle))
                if row['label'] == 'nonlinear_silent_right': coef[i, 1] = 0
                if row['label'] == 'nonlinear_zero': coef[i] = 0
            check('analytic_coefficients', z['coefficients'], coef)
            native = analytic(np.arange(38400, dtype=np.longdouble)/48000, freq, z['coefficients'])
            scale = float(np.sum(abs(coef)))
            check('entire_native_analytic_source', z['native'], native, gate=2e-11, scale=scale)
            assert float(z['source_start']) == 160.
            proof = verify(z, z['native'], 160., z['positions'], check)
            truth = analytic(np.asarray(z['positions'], np.longdouble)-160, freq, z['coefficients'], z['taps'])
            check('analytic_filtered_truth', z['truth'], truth, gate=2e-11, scale=scale)
            check('analytic_sampling_accuracy', z['audio'], truth, gate=2e-10, scale=scale)
            if row['label'] in ('nonlinear_zero', 'nonlinear_silent_right'): assert not np.count_nonzero(z['audio'][:, 1])
            r['cases'].append(dict(label=row['label'], sampling=proof, independently_verified=True))
            save(a.out/'report.json', r); print('C1_SAMPLING_INDEPENDENT', row['label'], flush=True)
        r.update(result='independent_c1_sampling_known_verified', verification_passed=True, all_qualified=True,
            no_producer_sampling_or_adapter_imports=True, material_read=False)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
