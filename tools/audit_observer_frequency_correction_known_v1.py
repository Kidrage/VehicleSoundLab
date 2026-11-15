"""Independent explicit weighted matrices check every saved correction result."""
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
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_frequency_v1/audit_oracle.py', 'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers): shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], material_read=False)
    try:
        record = load(a.study/'report.json'); assert record['result'] == 'observer_frequency_correction_known_ready'
        for name, digest in record['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for name, digest in record['inputs'].items(): assert sha(name) == digest
        for case in record['cases']:
            path = a.study/case['file']; assert sha(path) == case['sha256']
            with np.load(path) as z:
                _, _, weights, _, _ = metric(z['audio'], 64.)
                assert np.max(abs(weights-z['weights'])) < 2e-9*weights.max()
                gradients, firsts, objectives, initial_objectives, initial_gradients = [], [], [], [], []
                exacts, solutions = [], []
                for c in range(z['audio'].shape[1]):
                    systems, _, _ = matrices(z['positions'], z['orders'], z['scale'], z['audio'][:, c:c+1], weights, 1.)
                    A, b = systems['weighted_frame']
                    q = z['nodes'][:, :, c]/z['scale'][:, 0][None]
                    q0 = z['initial_nodes'][:, :, c]/z['scale'][:, 0][None]
                    x = np.r_[q.real.ravel(), q.imag.ravel()]
                    x0 = np.r_[q0.real.ravel(), q0.imag.ravel()]
                    truth = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
                    exacts.append(truth); solutions.append(x)
                    residual, initial = A@x-b, A@x0-b
                    gradients.append(A.T@residual); initial_gradients.append(A.T@initial); firsts.append(A.T@b)
                    objectives.append(residual@residual); initial_objectives.append(initial@initial)
                error = np.linalg.norm(np.array(solutions)-exacts)/np.linalg.norm(exacts)
                g = np.linalg.norm(gradients)/np.linalg.norm(firsts)
                ig = np.linalg.norm(initial_gradients)/np.linalg.norm(firsts)
                objective, initial = float(sum(objectives)), float(sum(initial_objectives))
                assert error < 2e-7 and g < 2e-7 and case['solve']['stop'] in (1, 2, 4, 5)
                assert abs(g-case['solve']['relative_stationarity']) < 2e-9
                assert abs(ig-case['solve']['initial_relative_stationarity']) < 2e-9
                assert abs(objective-case['solve']['objective']) < 2e-9*max(1., objective)
                assert abs(initial-case['solve']['initial_objective']) < 2e-9*max(1., initial)
                assert objective <= initial*(1+2e-10)+1e-20
                assert case['solve']['same_weighted_objective'] and not case['solve']['equivalent_saved_right_map']
                r['cases'].append(dict(label=case['label'], dense_relative_error=float(error), relative_stationarity=float(g)))
        assert record['zero_rhs_exact'] and record['zero_stop_code'] == 0
        r.update(result='independent_observer_frequency_correction_known_passed',
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo/n) for n in helpers})
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
