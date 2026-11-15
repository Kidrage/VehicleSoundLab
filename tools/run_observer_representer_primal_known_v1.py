"""Same four frozen failed-dual fixtures, one penalty-whitened primal attempt each."""
import argparse, copy, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_representer_v1.fixtures import DenseFixture
    from observer_representer_v1.primal import PenaltyPrimal, infer
    from observer_inverse_v1.fit import real_vector
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[], material_read=False, actual_supported_metric=False)
    try:
        old, audit = load(a.original/'report.json'), load(a.audit/'report.json')
        assert audit['result'] == 'independent_observer_representer_algebra_passed'
        assert audit['dense_equivalence_all_qualified'] and not audit['all_qualified']
        assert audit['producer_sha256'] == sha(a.original/'report.json')
        for path in (a.original/'report.json', a.audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        names = tuple(old['sources'])+('tools/run_observer_representer_primal_known_v1.py',
            'tools/observer_representer_v1/primal.py', 'research/observer_representer_primal_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        for old_case in old['cases']:
            path = a.original/old_case['file']
            assert sha(path) == old_case['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as z:
                capture = {k:z[k] for k in z.files if k not in ('probe', 'test', 'forward', 'backward')}
            system = DenseFixture(old_case['channels'], old_case['weak'], old_case['silent_right'])
            assert np.array_equal(system.A, capture['A']) and np.array_equal(system.audio, capture['audio'])
            fitted, u, info, old_cert, cert = infer(system, system.audio)
            q = real_vector(fitted/system.scale[None])
            exact = capture['original']
            residual = system@q-system.rhs(system.audio)
            stats = copy.deepcopy(old_case['stats'])
            del stats['iterative_dual']
            stats['iterative_primal'] = dict(dense_relative_error=float(np.linalg.norm(q-exact)/np.linalg.norm(exact)),
                relative_stationarity=info['relative_stationarity'], objective=float(residual@residual))
            qualified = bool(stats['iterative_primal']['dense_relative_error'] < 2e-7 and info['converged']
                and old_cert['additional_gap_gate_passed'] and cert['additional_gap_gate_passed'])
            primal = PenaltyPrimal(system)
            rng = np.random.default_rng(758934)
            probe, test = rng.normal(size=primal.shape[1]), rng.normal(size=primal.shape[0])
            capture.update(iterative=q, u=u, primal_probe=probe, primal_test=test,
                primal_forward=primal@probe, primal_backward=primal.rmatvec(test))
            dest = a.out/old_case['file']
            np.savez_compressed(dest, **capture)
            row = copy.deepcopy(old_case)
            row.update(file=dest.name, sha256=sha(dest), stats=stats, iterative_tag='iterative_primal',
                iterative_solve=info, residual_certificate=old_cert, representer_certificate=cert,
                qualified=qualified, previous_failed_dual_retained=True)
            r['cases'].append(row)
            save(a.out/'report.json', r)
            print('PRIMAL ALGEBRA', row['label'], qualified, stats['iterative_primal'], info, flush=True)
        r.update(result='observer_representer_primal_algebra_measured', all_qualified=all(c['qualified'] for c in r['cases']),
            actual_supported_metric_or_full_or_source_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
