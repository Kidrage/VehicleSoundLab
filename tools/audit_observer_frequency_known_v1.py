"""Independent SciPy, scalar-basis and dense-solve qualification before sources."""
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
    from observer_frequency_v1.audit_oracle import metric, frame_adjoint, matrices
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_frequency_v1/audit_oracle.py', 'tools/observer_complete_v1/audit_oracle.py')
    for j, name in enumerate(helpers): shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', cases=[], controls=[], material_read=False, maximum_errors={})
    def close(name, left, right, scale=1., gate=2e-9):
        err = float(np.max(abs(np.asarray(left)-right)/scale))
        assert err < gate, (name, err)
        r['maximum_errors'][name] = max(err, r['maximum_errors'].get(name, 0.))
    try:
        producer = load(a.study/'report.json')
        assert producer['result'] == 'observer_frequency_known_ready' and not producer['material_read']
        for name, digest in producer['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        for desc in producer['controls']:
            if 'file' not in desc: continue
            path = a.study/desc['file']; assert sha(path) == desc['sha256']
            with np.load(path) as z:
                rows, cover, weights, power, bands = metric(z['audio'], 64.)
                close('weights', weights, z['weights'], np.maximum(weights, 1e-24), 2e-12)
                close('band_power', power, z['band_power'], max(float(power.max()), 1e-24), 2e-12)
                assert np.array_equal(bands, z['bands'])
                rows *= weights[None, :, None]
                close('weighted_rows', rows, z['rows'], max(float(abs(rows).max()), 1e-24), 2e-12)
                normal = frame_adjoint(rows*weights[None, :, None], cover, len(z['audio']))
                close('metric_normal', normal, z['normal'], max(float(abs(normal).max()), 1e-24), 2e-12)
                r['controls'].append(desc['name'])
        path = a.study/'metric_controls.npz'; assert sha(path) == producer['metric_controls_sha256']
        with np.load(path) as z:
            rows, cover, weights, power, bands = metric(z['audio'], 64.)
            close('metric_control_rows', rows*weights[None, :, None], z['rows'], gate=2e-12)
            grad = frame_adjoint(z['test']*weights[None, :, None], cover, len(z['audio']))
            close('metric_adjoint', grad, z['gradient'], gate=2e-11)
            close('real_adjoint_dot', np.vdot(z['rows'], z['test']).real,
                np.vdot(z['audio'], grad).real, max(1, abs(np.vdot(z['audio'], grad).real)), 2e-12)
            for transform in (np.array([[0., 1.], [1., 0.]]), np.array([[.6, .8], [-.8, .6]])):
                other, _, w, _, _ = metric(z['audio']@transform, 64.)
                close('orthogonal_shared_weights', w, weights, weights, 2e-12)
                close('orthogonal_rows', other*w[None, :, None], (rows*weights[None, :, None])@transform, gate=2e-12)
            other, _, w, _, _ = metric(z['audio']*3.7, 64.)
            close('positive_scale', other*w[None, :, None], rows*weights[None, :, None], gate=2e-12)
            uniform = frame_adjoint(rows*6.25, cover, len(z['audio']))
            close('uniform_Parseval', uniform, z['audio']*6.25, gate=2e-12)
        for desc in producer['cases']:
            path = a.study/desc['file']; assert sha(path) == desc['sha256']
            with np.load(path) as z:
                rows, cover, weights, power, bands = metric(z['audio'], 64.)
                close('case_weights', weights, z['weights'], weights, 2e-12)
                systems, Phi, D = matrices(z['positions'], z['orders'], z['scale'], z['audio'], weights, float(z['sigma']))
                shape = z['source_nodes'].shape
                def vector(nodes):
                    q = nodes/z['scale'][None]
                    return np.r_[q.real.ravel(), q.imag.ravel()]
                origin = vector(z['source_nodes'])
                close('explicit_source', (Phi@origin).reshape(z['audio'].shape), z['audio'], gate=2e-12)
                size = len(origin)//2
                highmask = np.tile(np.array([0., 1.]), len(z['positions']))
                mask = np.r_[highmask, highmask]
                high_truth = Phi@(origin*mask)
                oracle = {}
                for tag, (A, b) in systems.items():
                    G = A.T@A; rhs = A.T@b
                    scale = np.sqrt(np.diag(G)[:, None]*np.diag(G)[None])
                    close('dense_Gram', G, z[tag+'_normal_matrix'], np.maximum(scale, 1e-24), 2e-9)
                    close('dense_rhs', rhs, z[tag+'_normal_rhs'], np.maximum(np.sqrt(np.diag(G))*np.linalg.norm(b), 1e-24), 2e-9)
                    truth, _, rank, singular = linalg.lstsq(A, b, cond=None, lapack_driver='gelsd')
                    x = vector(z[tag+'_nodes'])
                    close('dense_solution', x, truth, max(np.linalg.norm(truth), 1e-24), 2e-7)
                    residual = A@x-b
                    stats = dict(wave_NRMSE=float(np.linalg.norm(Phi@x-z['audio'].ravel())/np.linalg.norm(z['audio'])),
                        high_component_NRMSE=float(np.linalg.norm(Phi@(x*mask)-high_truth)/np.linalg.norm(high_truth)),
                        objective=float(residual@residual),
                        relative_stationarity=float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b), 1e-24)),
                        dense_condition=float(singular[0]/singular[-1]))
                    for field, value in stats.items():
                        close('derived_'+field, value, desc['variants'][tag][field], max(1, abs(value)), 2e-7)
                    oracle[tag] = stats
                A, b = systems['weighted_frame']
                T = linalg.solve_triangular(np.linalg.cholesky(.001*D.T@D+.000001*np.eye(len(D)+2)).T,
                    np.eye(len(D)+2), lower=False)
                time = linalg.block_diag(np.kron(T, np.eye(2)), np.kron(T, np.eye(2)))
                w = np.tile(weights[4*z['orders']], len(z['positions']))
                P = time/np.sqrt(1+np.sum((Phi@time)**2, axis=0)*np.r_[w, w]**2)[None]
                close('right_map', P, z['right'], max(float(abs(P).max()), 1e-24), 2e-10)
                for budget in (8, 4000):
                    tag = f'iterative_{budget}'; x = vector(z[tag+'_nodes'])
                    dense = vector(z['weighted_frame_nodes'])
                    error = float(np.linalg.norm(x-dense)/np.linalg.norm(dense))
                    close('iterative_dense_error', error, desc['variants'][tag]['dense_relative_error'], gate=2e-9)
                    residual = A@x-b
                    stationarity = float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b), 1e-24))
                    close('iterative_stationarity', stationarity, desc['variants'][tag]['relative_stationarity'], gate=2e-9)
                    converged = desc['variants'][tag]['stop'] in (1, 2, 4, 5) and stationarity < 2e-7
                    assert converged == desc['variants'][tag]['converged']
                    if budget == 4000: assert converged and error < 2e-7
                    for field, value in dict(objective=float(residual@residual),
                        wave_NRMSE=float(np.linalg.norm(Phi@x-z['audio'].ravel())/np.linalg.norm(z['audio'])),
                        high_component_NRMSE=float(np.linalg.norm(Phi@(x*mask)-high_truth)/np.linalg.norm(high_truth))).items():
                        close('iterative_'+field, value, desc['variants'][tag][field], max(1, abs(value)), 2e-7)
                r['cases'].append(dict(label=desc['label'], exact_variants=oracle))
            save(a.out/'report.json', r)
            print('AUDITED frequency known', desc['label'], flush=True)
        assert len(r['cases']) == 6
        r.update(result='independent_observer_frequency_known_passed',
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo/n) for n in helpers})
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
