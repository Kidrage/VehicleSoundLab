"""Qualify a new right map with dense separated/neighbor/zero controls, no sources."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'): p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.sparse.linalg import LinearOperator, lsmr
    from scipy import linalg
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem, FrequencyRight
    from observer_frequency_v1.block_right import OrderBlockRight
    from observer_inverse_v1.fit import real_vector, complex_array
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    names = ('tools/run_observer_frequency_block_known_v1.py', 'tools/observer_frequency_v1/block_right.py',
        'tools/observer_frequency_v1/metric.py', 'tools/observer_frequency_v1/fit.py',
        'tools/observer_complete_v1/synthesis.py', 'tools/observer_complete_v1/frame.py',
        'tools/observer_complete_v1/fit.py', 'tools/observer_inverse_v1/fit.py',
        'tools/observer_inverse_v1/regularizer.py', 'tools/observer_inverse_v1/refinement.py',
        'tools/observer_forward_v1/operator.py', 'tools/observer_forward_v1/polyphase.py')
    r = dict(result='running', sources={}, cases=[], material_read=False)
    for name in names:
        dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
    try:
        rng = np.random.default_rng(721164)
        N = 4353; positions = np.rint(np.linspace(0, N-1, 9)).astype(int)
        for label, orders in (('separated', np.array([7, 211])), ('neighbors', np.array([7, 8, 211, 212]))):
            s = WaveSynthesis(N, positions, orders, 1)
            scale = np.where(orders < 100, 1., .0001)[:, None]
            source = (rng.normal(size=s.shape)+1j*rng.normal(size=s.shape))*scale[None]
            audio = s.synthesize(source); metric = FrequencyMetric(audio, 64.)
            system = WeightedSystem(s, scale, metric)
            A = np.column_stack([system@x for x in np.eye(system.nsize)]); b = system.rhs(audio)
            right = OrderBlockRight(system)
            P = np.column_stack([right.apply(x) for x in np.eye(system.nsize)])
            old = FrequencyRight(system)
            oldP = np.column_stack([old.apply(x) for x in np.eye(system.nsize)])
            u = rng.normal(size=system.nsize); v = rng.normal(size=system.nsize)
            assert abs(np.dot(right.apply(u), v)-np.dot(u, right.transpose(v))) < 2e-9
            assert np.linalg.svd(P, compute_uv=False).min() > 0
            transformed = LinearOperator(system.shape, matvec=lambda u: system@right.apply(u),
                rmatvec=lambda y: right.transpose(system.rmatvec(y)), dtype=float)
            result = lsmr(transformed, b, atol=1e-11, btol=1e-11, conlim=1e12, maxiter=4000)
            x = right.apply(result[0]); truth = linalg.lstsq(A, b, lapack_driver='gelsd')[0]
            error = float(np.linalg.norm(x-truth)/np.linalg.norm(truth))
            gradient = float(np.linalg.norm(A.T@(A@x-b))/np.linalg.norm(A.T@b))
            assert result[1] in (1, 2, 4, 5) and gradient < 2e-7 and error < 2e-7
            zero = lsmr(transformed, np.zeros_like(b), atol=1e-11, btol=1e-11, maxiter=4000)
            assert zero[1] == 0 and not np.any(zero[0])
            path = a.out/(label+'.npz')
            np.savez_compressed(path, source_nodes=source, audio=audio, scale=scale, orders=orders,
                positions=positions, weights=metric.weights, right_matrix=right.matrix,
                P=P, oldP=oldP, normal_matrix=A.T@A, normal_rhs=A.T@b, solution=x, dense_solution=truth)
            row = dict(label=label, file=path.name, sha256=sha(path), condition=float(np.linalg.cond(A)),
                old_condition=float(np.linalg.cond(A@oldP)), block_condition=float(np.linalg.cond(A@P)),
                iterations=int(result[2]), stop=int(result[1]), relative_stationarity=gradient, dense_relative_error=error)
            r['cases'].append(row); print('BLOCK KNOWN', row, flush=True)
        stereo = WaveSynthesis(N, positions, orders, 2)
        stereo_audio = np.column_stack((audio[:, 0], .3*audio[:, 0]+.05*np.sin(np.arange(N)*.019)))
        stereo_metric = FrequencyMetric(stereo_audio, 64.)
        stereo_system = WeightedSystem(stereo, scale, stereo_metric)
        right = OrderBlockRight(stereo_system)
        u = rng.normal(size=stereo_system.nsize); v = rng.normal(size=stereo_system.nsize)
        forward = right.apply(u); backward = right.transpose(v)
        assert abs(np.dot(forward, v)-np.dot(u, backward)) < 2e-9
        path = a.out/'stereo_map.npz'
        np.savez_compressed(path, audio=stereo_audio, positions=positions, orders=orders, scale=scale,
            matrix=right.matrix, weights=stereo_metric.weights, u=u, v=v, forward=forward, backward=backward)
        r['stereo_map_sha256'] = sha(path)
        r.update(result='observer_frequency_block_known_ready')
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
