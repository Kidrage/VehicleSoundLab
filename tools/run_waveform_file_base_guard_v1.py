"""Qualify only the new full base-root diagnostic against seven frozen controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


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
    from waveform_banded_v1.metric import BandedMetric
    from waveform_structured_v1.resources import ArrayLedger
    from waveform_file_full_v1.base_guard import inspect
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={})
    for name in ('tools/run_waveform_file_base_guard_v1.py',
                 'tools/waveform_file_full_v1/base_guard.py',
                 'tools/waveform_banded_v1/root.py', 'tools/waveform_banded_v1/metric.py',
                 'tools/waveform_structured_v1/resources.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)
    try:
        archive = a.workspace/'baselines/waveform_file_panels_v1'
        manifest = {x['path']:x['sha256'] for x in load(archive/'manifest.json')['files']}
        root = archive/'evidence/controls3'
        producer = load(root/'report.json')
        r['inputs'][str(root/'report.json')] = sha(root/'report.json')
        assert r['inputs'][str(root/'report.json')] == manifest['evidence/controls3/report.json']
        class Prior:
            def __init__(self, R): self.L = np.linalg.cholesky(R)
            def inverse(self, x): return linalg.solve_triangular(self.L, x, lower=True)
        for case in producer['original_cases']:
            path = root/case['file']
            digest = sha(path)
            assert digest == case['sha256'] == manifest['evidence/controls3/'+path.name]
            r['inputs'][str(path)] = digest
            with np.load(path) as z:
                Phi, W, R, y = (z[n] for n in ('Phi', 'W', 'R', 'y'))
                Lw, prior = np.linalg.cholesky(W), Prior(R)
                X = linalg.solve_triangular(prior.L, (Lw.T@Phi).T, lower=True).T
                normA = float(np.sqrt(np.sum(X*X)+len(R)))
                base = dict(z=z['base_z'], wave_model_residual=z['base_wave'],
                    q=linalg.solve_triangular(prior.L.T, z['base_z'], lower=False))
                metric, ledger = BandedMetric.control_from_dense(W), ArrayLedger()
                root_view = metric.factor(ledger)
                info = dict(metric_root_shares_input=root_view.shares_input, augmented_root_Frobenius=normA)
                got = inspect(metric, info, base, y, lambda x:Phi@x, lambda x:Phi.T@x, prior, ledger)
                model = Lw.T@base['wave_model_residual']
                normal = linalg.solve_triangular(prior.L, Phi.T@W@base['wave_model_residual'], lower=True)+base['z']
                denominator = normA*np.sqrt(np.sum(model*model, axis=0)+np.sum(base['z']**2, axis=0))
                expected_stable = np.linalg.norm(normal, axis=0)/np.maximum(denominator, 1e-300)
                expected_back = np.linalg.norm(Lw.T@(Phi@base['q']-y)-model, axis=0)/np.maximum(np.linalg.norm(Lw.T@y, axis=0), 1e-300)
                stable_error = float(np.max(abs(expected_stable-got['stable_root_normal_relative'])))
                back_error = float(np.max(abs(expected_back-got['root_backward_discrepancy'])))
                assert stable_error < 2e-12 and back_error < 2e-12
                assert got['stable_root_guard_passed'] and np.all(expected_stable <= 1e-11) and np.all(expected_back <= 1e-11)
                guards = []
                for bad in ('alias', 'consumed'):
                    modified = dict(info)
                    if bad == 'alias': modified['metric_root_shares_input'] = False
                    else: metric.consumed = False
                    try:
                        inspect(metric, modified, base, y, lambda x:Phi@x, lambda x:Phi.T@x, prior, ledger)
                    except RuntimeError: guards.append(bad)
                    else: raise AssertionError(('accepted invalid diagnostic owner', bad))
                    metric.consumed = True
                changed = dict(base, wave_model_residual=base['wave_model_residual']+0.001)
                reject = inspect(metric, info, changed, y, lambda x:Phi@x, lambda x:Phi.T@x, prior, ledger)
                assert not reject['stable_root_guard_passed']
                r['cases'].append(dict(label=case['label'], qualified=True, diagnostic=got,
                    independent_stable=expected_stable.tolist(), independent_backward=expected_back.tolist(),
                    stable_absolute_error=stable_error, backward_absolute_error=back_error,
                    ownership_rejections=guards, perturbed_waveform_rejected=True))
        assert len(r['cases']) == 7
        r.update(result='independent_waveform_file_base_guard_verified', all_qualified=True,
                 no_file_kernel_or_known_pipeline_rerun=True)
        save(a.out/'report.json', r)
        print(r['result'], len(r['cases']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__': main()
