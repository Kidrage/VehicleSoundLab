"""One full288 stereo/quarter-cycle synthetic gate after independent context audit."""
import argparse, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'context-audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_inverse_v1.fit import real_vector
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem, SupportedBlockRight, infer_target
    from observer_frequency_v1.optimality import bound
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, material_read=False)
    try:
        audit = load(a.context_audit / 'report.json')
        assert audit['result'] == 'independent_observer_context_known_passed'
        assert audit['all_target_fidelity_qualified'] and audit['all_solver_qualified']
        r['inputs'][str(a.context_audit / 'report.json')] = sha(a.context_audit / 'report.json')
        context = load(a.context_audit.parent / 'context1/report.json')
        assert sha(a.context_audit.parent / 'context1/report.json') == audit['producer_sha256']
        names = tuple(context['sources']) + ('tools/run_observer_supported_full_known_v1.py',
            'research/observer_supported_full_known_v1_plan.json')
        for name in names:
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest)
            r['sources'][name] = sha(dest)
        print('SUPPORTED_FULL_KNOWN_PID', os.getpid(), flush=True)
        orders = np.arange(1, 289)
        positions = np.arange(49) * 256
        indices = np.arange(-8, 41)
        factors = np.sin(indices[:, None] * np.arange(1, 13)[None] * .071)
        h, k, c = orders[:, None, None], np.arange(1, 13)[None, :, None], np.arange(2)[None, None, :]
        loadings = (np.cos(h*k*.113 + c*.47) + .3j*np.sin(h*(k+1)*.079+c*.91)) / np.sqrt(12)
        base = np.exp(1j*(orders[:, None]*.173+np.arange(2)[None]*.37))
        normalized = base[None] * (1 + .12 * np.einsum('mk,hkc->mhc', factors, loadings))
        scale = (orders.astype(float)**-1.15 * np.where(orders >= 126, .1, 1.))[:, None]
        rotation = np.exp(-2j*np.pi*((orders*2048) % 1024)/1024)
        nodes = normalized * scale[None] * rotation[None, :, None]
        synth = WaveSynthesis(12289, positions, orders, 2)
        audio = synth.synthesize(nodes)
        metric = SupportedMetric(audio, 64.)
        system = SupportedSystem(synth, scale, metric)
        right = SupportedBlockRight(system)
        rng = np.random.default_rng(651182)
        u, v = rng.normal(size=system.nsize), rng.normal(size=system.shape[0])
        forward, backward = system @ u, system.rmatvec(v)
        dot_error = float(abs(forward@v-u@backward)/max(1., abs(forward@v)))
        assert dot_error < 2e-11
        right_u, right_v = right.apply(u), right.transpose(u)
        started = time.monotonic()
        fitted, info, right = infer_target(system, audio, maxiter=4000)
        elapsed = time.monotonic() - started
        wave = synth.synthesize(fitted)
        residual = wave - audio
        rows, reference = metric.forward(residual), metric.forward(audio)
        starts = metric.frame.starts[metric.keep]
        central = (starts >= 2048) & (starts + 4096 <= 10241)
        assert central.sum() == 17
        band_errors = []
        whole_band_errors = []
        for band in range(6):
            mask = metric.bands == band
            band_errors.append(float(np.linalg.norm(rows[central][:, mask]) / np.linalg.norm(reference[central][:, mask])))
            whole_band_errors.append(float(np.linalg.norm(rows[:, mask]) / np.linalg.norm(reference[:, mask])))
        metrics = dict(whole_wave_NRMSE=float(np.linalg.norm(residual)/np.linalg.norm(audio)),
            target_wave_NRMSE=float(np.linalg.norm(residual[2048:10241])/np.linalg.norm(audio[2048:10241])),
            target_supported_band_complex_NRMSE=band_errors, whole_supported_band_complex_NRMSE=whole_band_errors,
            whole_wave_regions_NRMSE=[float(np.linalg.norm(residual[s])/np.linalg.norm(audio[s]))
                for s in (slice(0, 2048), slice(2048, 10241), slice(10241, None))])
        cert = bound(system, audio, fitted)
        path = a.out / 'capture.npz'
        np.savez_compressed(path, audio=audio, positions=positions, orders=orders, scale=scale, nodes=nodes,
            factors=factors, loadings=loadings, fitted=fitted, wave=wave, weights=metric.weights,
            band_power=metric.band_power, floor_active=metric.floor_active, right_matrix=right.matrix,
            probe_u=u, probe_v=v, forward=forward, backward=backward, right_u=right_u, right_v=right_v)
        r.update(result='observer_supported_full_known_measured', frames=12289, target_frames=8193,
            offset=2048, harmonics=288, channels=2, factors=12, node_count=49, node_step=256,
            capture_sha256=sha(path), solver=info, certificate=cert, metrics=metrics,
            system_adjoint_error=dot_error, solve_wall_seconds=elapsed,
            solver_qualified=bool(info['converged'] and cert['additional_gap_gate_passed']),
            fidelity_qualified=bool(metrics['target_wave_NRMSE'] < .02 and max(band_errors) < .02),
            only_one_attempt=True, source_or_runtime_or_hearing_promoted=False)
        save(a.out / 'report.json', r)
        print(r['result'], 'solver', r['solver_qualified'], 'fidelity', r['fidelity_qualified'], flush=True)
        print(info, metrics, cert, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
