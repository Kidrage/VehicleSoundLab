"""Known-first exact-objective bias versus finite-iteration error, no source reads."""
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
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_complete_v1.fit import CompleteSystem
    from observer_inverse_v1.fit import real_vector, complex_array, RegularizedObserver
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem, FrequencyRight, infer
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    sources = ('research/observer_frequency_metric_known_v1_plan.json',
        'tools/run_observer_frequency_known_v1.py', 'tools/observer_frequency_v1/metric.py',
        'tools/observer_frequency_v1/fit.py', 'tools/observer_complete_v1/frame.py',
        'tools/observer_complete_v1/synthesis.py', 'tools/observer_complete_v1/fit.py',
        'tools/observer_forward_v1/operator.py', 'tools/observer_forward_v1/polyphase.py',
        'tools/observer_inverse_v1/fit.py', 'tools/observer_inverse_v1/regularizer.py',
        'tools/observer_inverse_v1/refinement.py')
    r = dict(result='running', pid=os.getpid(), sources={}, controls=[], cases=[], material_read=False)
    for name in sources:
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)
    print('FREQUENCY_KNOWN_PID', os.getpid(), flush=True)
    try:
        rng = np.random.default_rng(261151)
        N = 4353; n = np.arange(N); positions = np.rint(np.linspace(0, N-1, 9)).astype(int)
        orders = np.array([7, 211]); root = 64.
        audio = rng.normal(size=(N, 2))
        metric = FrequencyMetric(audio, root)
        test = rng.normal(size=metric.shape)+1j*rng.normal(size=metric.shape)
        left, right = np.vdot(metric.forward(audio), test).real, np.vdot(audio, metric.adjoint(test)).real
        adjoint = abs(left-right)/max(1, abs(left)); assert adjoint < 2e-12
        r['controls'].append(dict(name='metric_adjoint', error=float(adjoint)))
        ref_weights = metric.weights.copy(); metric.weights[:] = 2.5
        err = float(abs(metric.normal(audio)-6.25*audio).max()); assert err < 2e-12
        r['controls'].append(dict(name='uniform_metric_Parseval', error=err))
        metric.weights[:] = ref_weights
        for label, transform in (('swap', np.array([[0., 1.], [1., 0.]])),
                                 ('rotate', np.array([[.6, .8], [-.8, .6]]))):
            other = FrequencyMetric(audio@transform, root)
            err = float(np.max(abs(other.weights/metric.weights-1))); assert err < 2e-12
            close = float(abs(other.forward(audio@transform)-metric.forward(audio)@transform).max())
            assert close < 2e-12
            r['controls'].append(dict(name='shared_LR_'+label, error=err, row_error=close))
        other = FrequencyMetric(audio*3.7, root)
        err = float(abs(other.forward(audio*3.7)-metric.forward(audio)).max()); assert err < 2e-12
        r['controls'].append(dict(name='positive_scale', error=err))
        for label in ('first', 'last', 'between_HF', 'silent_right', 'zero'):
            wave = np.zeros((N, 2))
            if label == 'first': wave[0] = [1., -.2]
            elif label == 'last': wave[-1] = [-.4, .7]
            elif label == 'between_HF':
                wave[:, 0] = np.cos(2*np.pi*211.37*n/1024)
                wave[:, 1] = .4*np.cos(2*np.pi*212.61*n/1024+.3)
            elif label == 'silent_right': wave[:, 0] = audio[:, 0]
            met = FrequencyMetric(wave, root)
            rows = met.forward(wave); back = met.adjoint(rows)
            if label == 'zero': assert np.array_equal(met.weights, np.ones(2049)) and not np.any(rows) and not np.any(back)
            else: assert np.vdot(rows, rows).real > 0 and np.isfinite(back).all()
            if label == 'silent_right': assert not np.any(rows[:, :, 1]) and not np.any(back[:, 1])
            assert np.all(met.weights > 0)
            if not met.silent:
                assert met.weights.max()*np.sqrt(met.global_power) <= 1e4*(1+1e-12)
            path = a.out/('control_'+label+'.npz')
            np.savez_compressed(path, audio=wave, weights=met.weights, bands=met.bands,
                band_power=met.band_power, rows=rows, normal=back)
            r['controls'].append(dict(name=label, file=path.name, sha256=sha(path)))
        np.savez_compressed(a.out/'metric_controls.npz', audio=audio, test=test,
            weights=metric.weights, rows=metric.forward(audio), gradient=metric.adjoint(test))
        r['metric_controls_sha256'] = sha(a.out/'metric_controls.npz')
        synthesis = WaveSynthesis(N, positions, orders, 1)
        for weak in (1., .01, .0001):
            scale = np.array([[1.], [weak]])
            for law in ('constant', 'curved'):
                label = f'{law}_{weak:g}'; folder = a.out/label; folder.mkdir()
                q = np.ones(synthesis.shape, complex)
                q[:, 0, 0] = 1.+.15j
                q[:, 1, 0] = (1.+.3j if law == 'constant' else
                    1.+.8*np.cos(np.arange(len(positions))*np.pi)+.3j*np.sin(np.arange(len(positions))*.9))
                nodes = q*scale[None]; audio = synthesis.synthesize(nodes)
                met = FrequencyMetric(audio, root)
                sigma = float(np.sqrt(np.mean(audio**2)))
                old = RegularizedObserver(synthesis.operator, scale)
                full = CompleteSystem(synthesis, scale, sigma)
                weighted = WeightedSystem(synthesis, scale, met)
                case = dict(label=label, weak_amplitude=weak, law=law, variants={}, band_power=met.band_power.tolist())
                def describe(fitted):
                    mask = np.array([0., 1.])[None, :, None]
                    truth = synthesis.synthesize(nodes*mask)
                    high = synthesis.synthesize(fitted*mask)
                    return dict(wave_NRMSE=float(np.linalg.norm(synthesis.synthesize(fitted)-audio)/np.linalg.norm(audio)),
                        high_component_NRMSE=float(np.linalg.norm(high-truth)/np.linalg.norm(truth)))
                values = dict(source_nodes=nodes, audio=audio, positions=positions, orders=orders,
                    scale=scale, weights=met.weights, band_power=met.band_power, sigma=sigma)
                for tag, system, target in (('old_harmonic', old, old.observer.forward(nodes)),
                    ('global_wave', full, audio), ('weighted_frame', weighted, audio)):
                    A = np.column_stack([system@x for x in np.eye(system.nsize)])
                    b = system.rhs(target)
                    x, residuals, rank, singular = linalg.lstsq(A, b, cond=None, lapack_driver='gelsd')
                    assert rank == system.nsize
                    fitted = complex_array(x, synthesis.shape)*scale[None]
                    residual = A@x-b
                    stationarity = float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b), 1e-24))
                    assert stationarity < 2e-9
                    values.update({tag+'_nodes': fitted, tag+'_normal_matrix': A.T@A,
                        tag+'_normal_rhs': A.T@b, tag+'_singular_values': singular})
                    case['variants'][tag] = dict(**describe(fitted), objective=float(residual@residual),
                        relative_stationarity=stationarity, dense_condition=float(singular[0]/singular[-1]))
                    if tag == 'weighted_frame':
                        right = FrequencyRight(system)
                        P = np.column_stack([right.apply(v) for v in np.eye(system.nsize)])
                        u = rng.normal(size=system.nsize); v = rng.normal(size=system.shape[0])
                        adj = float(abs(np.dot(system@u, v)-np.dot(u, system.rmatvec(v)))/max(1, abs(np.dot(system@u, v))))
                        assert adj < 2e-11
                        assert np.linalg.svd(P, compute_uv=False).min() > 0
                        assert abs(P.T@u-right.transpose(u)).max() < 2e-10
                        values['right'] = P
                        case['system_adjoint_error'] = adj
                        case['preconditioned_dense_condition'] = float(np.linalg.cond(A@P))
                for budget in (8, 4000):
                    fitted, info, right = infer(synthesis, audio, scale, met, maxiter=budget)
                    exact = values['weighted_frame_nodes']
                    error = float(np.linalg.norm((fitted-exact)/scale[None])/max(np.linalg.norm(exact/scale[None]), 1e-24))
                    case['variants'][f'iterative_{budget}'] = dict(**info, **describe(fitted), dense_relative_error=error)
                    values[f'iterative_{budget}_nodes'] = fitted
                    if budget == 4000: assert info['converged'] and error < 2e-7, (label, info, error)
                path = folder/'capture.npz'; np.savez_compressed(path, **values)
                case.update(file=label+'/capture.npz', sha256=sha(path)); r['cases'].append(case)
                save(a.out/'report.json', r)
                print('FREQUENCY KNOWN', label, 'exact_high_global/weighted',
                    case['variants']['global_wave']['high_component_NRMSE'],
                    case['variants']['weighted_frame']['high_component_NRMSE'], flush=True)
        r.update(result='observer_frequency_known_ready', dense_cases=6, material_read=False)
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
