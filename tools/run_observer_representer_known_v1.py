"""Four explicit algebra controls before any original-metric representer experiment."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import save, sha


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
    from observer_representer_v1.fixtures import DenseFixture
    from observer_representer_v1.dual import ObservationDual, infer, representer_certificate
    from observer_inverse_v1.fit import real_vector, complex_array
    from observer_frequency_v1.optimality import bound
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, cases=[], material_read=False, actual_supported_metric=False)
    names = ('tools/run_observer_representer_known_v1.py', 'tools/observer_representer_v1/fixtures.py',
        'tools/observer_representer_v1/dual.py', 'research/observer_representer_known_v1_plan.json',
        'research/observer_representer_v1_plan.json', 'tools/observer_frequency_v1/optimality.py',
        'tools/observer_inverse_v1/fit.py')
    for name in names:
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)
    try:
        for label, channels, weak, silent in (('mono', 1, .0001, False),
                ('stereo', 2, .0001, False), ('weak1e-5', 2, .00001, False), ('silent_right', 2, .0001, True)):
            system = DenseFixture(channels, weak, silent)
            audio = system.audio
            b = system.rhs(audio)
            exact = linalg.lstsq(system.A, b, lapack_driver='gelsd')[0]
            dual = ObservationDual(system)
            T = np.column_stack([dual.prior.apply(x) for x in np.eye(system.nsize)])
            A = system.B@T
            G = np.vstack((A.T, np.eye(system.ysize)))
            target = np.r_[np.zeros(system.nsize), b[:system.ysize]]
            dense_u = linalg.lstsq(G, target, lapack_driver='gelsd')[0]
            dense_q = T@(A.T@dense_u)
            Hinv = linalg.solve(system.wave_metric, np.eye(system.ysize), assume_a='pos')
            Rphi = linalg.solve(system.R, system.Phi.T, assume_a='pos')
            plain = Hinv+system.Phi@Rphi
            w = linalg.solve(plain, audio.ravel(), assume_a='pos')
            plain_q = Rphi@w
            fitted, u, info, old_cert, cert = infer(system, audio)
            fitted_q = real_vector(fitted/system.scale[None])
            rng = np.random.default_rng(758934)
            probe = rng.normal(size=system.ysize)
            test = rng.normal(size=dual.shape[0])
            forward, backward = dual@probe, dual.rmatvec(test)
            assert abs(forward@test-probe@backward)/max(1., abs(forward@test)) < 2e-11
            _, singular, vh = linalg.svd(system.Phi, full_matrices=True)
            null = vh[system.ysize:].T
            assert np.max(abs(system.Phi@null)) < 2e-11
            data_null_penalty_gradient = float(np.linalg.norm(null.T@(system.R@dense_q)))
            stats = {}
            for name, q in (('original', exact), ('dense_dual', dense_q), ('iterative_dual', fitted_q), ('plain_sample_normal', plain_q)):
                residual = system.A@q-b
                stats[name] = dict(dense_relative_error=float(np.linalg.norm(q-exact)/np.linalg.norm(exact)),
                    relative_stationarity=float(np.linalg.norm(system.A.T@residual)/np.linalg.norm(system.A.T@b)),
                    objective=float(residual@residual))
            dense_nodes = complex_array(dense_q, system.nshape)*system.scale[None]
            dense_old_cert = bound(system, audio, dense_nodes)
            dense_cert = representer_certificate(system, audio, dense_nodes, dense_u)
            qualified = bool(stats['dense_dual']['dense_relative_error'] < 2e-7 and
                stats['dense_dual']['relative_stationarity'] < 2e-7 and stats['iterative_dual']['dense_relative_error'] < 2e-7
                and info['converged'] and old_cert['additional_gap_gate_passed'] and cert['additional_gap_gate_passed']
                and dense_old_cert['additional_gap_gate_passed'] and dense_cert['additional_gap_gate_passed'])
            path = a.out/(label+'.npz')
            np.savez_compressed(path, audio=audio, positions=system.positions, orders=system.orders,
                scale=system.scale, truth=system.truth, Phi=system.Phi, H=system.wave_metric, R=system.R,
                B=system.B, A=system.A, b=b, T=T, original=exact, dense_dual=dense_q, dense_u=dense_u,
                iterative=fitted_q, u=u, plain=plain_q, plain_w=w, sample_normal=plain,
                null_basis=null, singular_values=singular, probe=probe, test=test, forward=forward, backward=backward)
            row = dict(label=label, channels=channels, weak=weak, silent_right=silent,
                file=path.name, sha256=sha(path), stats=stats, iterative_solve=info,
                residual_certificate=old_cert, representer_certificate=cert,
                dense_residual_certificate=dense_old_cert, dense_representer_certificate=dense_cert,
                data_null_penalty_gradient=data_null_penalty_gradient,
                plain_sample_condition=float(np.linalg.cond(plain)), augmented_dual_condition=float(np.linalg.cond(G)),
                qualified=qualified, plain_normal_not_credited_as_stable=True)
            r['cases'].append(row)
            save(a.out/'report.json', r)
            print('REPRESENTER ALGEBRA', label, qualified, stats, info, flush=True)
        r.update(result='observer_representer_algebra_measured', all_qualified=all(c['qualified'] for c in r['cases']),
            actual_supported_metric_or_full_or_source_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
