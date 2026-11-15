"""One penalty-whitened solve of the identical frozen full288 problem."""
import argparse, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'prerequisite', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.primal import PenaltyPrimal, infer
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, material_read=False)
    try:
        old, audit = load(a.original/'report.json'), load(a.prerequisite/'report.json')
        assert old['result'] == 'observer_supported_full_known_measured' and not old['solver_qualified']
        assert audit['result'] == 'independent_observer_representer_context_passed' and audit['all_qualified']
        for path in (a.original/'report.json', a.original/'capture.npz', a.prerequisite/'report.json'):
            r['inputs'][str(path)] = sha(path)
        assert sha(a.original/'capture.npz') == old['capture_sha256']
        names = tuple(old['sources'])+('tools/run_observer_representer_full_v1.py',
            'tools/observer_representer_v1/dual.py', 'tools/observer_representer_v1/primal.py',
            'research/observer_representer_full_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        with np.load(a.original/'capture.npz') as z:
            capture = {n:z[n] for n in ('audio', 'positions', 'orders', 'scale', 'nodes', 'factors', 'loadings')}
        audio, positions, orders, scale = (capture[n] for n in ('audio', 'positions', 'orders', 'scale'))
        synthesis = WaveSynthesis(len(audio), positions, orders, 2)
        metric = SupportedMetric(audio, 64.)
        system = SupportedSystem(synthesis, scale, metric)
        primal = PenaltyPrimal(system)
        rng = np.random.default_rng(758934)
        probe, test = rng.normal(size=primal.shape[1]), rng.normal(size=primal.shape[0])
        capture.update(primal_probe=probe, primal_test=test, primal_forward=primal@probe,
            primal_backward=primal.rmatvec(test))
        print('REPRESENTER_FULL_PID', os.getpid(), flush=True)
        started = time.monotonic()
        fitted, u, info, residual_cert, repr_cert = infer(system, audio, maxiter=4000)
        elapsed = time.monotonic()-started
        wave = synthesis.synthesize(fitted)
        residual = wave-audio
        rows, reference = metric.forward(residual), metric.forward(audio)
        starts = metric.frame.starts[metric.keep]
        central = (starts >= 2048)&(starts+4096 <= 10241)
        metrics = dict(whole_wave_NRMSE=float(np.linalg.norm(residual)/np.linalg.norm(audio)),
            target_wave_NRMSE=float(np.linalg.norm(residual[2048:10241])/np.linalg.norm(audio[2048:10241])),
            target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:, metric.bands==b])/np.linalg.norm(reference[central][:, metric.bands==b])) for b in range(6)],
            whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:, metric.bands==b])/np.linalg.norm(reference[:, metric.bands==b])) for b in range(6)],
            whole_wave_regions_NRMSE=[float(np.linalg.norm(residual[s])/np.linalg.norm(audio[s])) for s in (slice(0, 2048), slice(2048, 10241), slice(10241, None))])
        capture.update(fitted=fitted, wave=wave, u=u, weights=metric.weights,
            band_power=metric.band_power, floor_active=metric.floor_active)
        np.savez_compressed(a.out/'capture.npz', **capture)
        r.update(result='observer_representer_full_known_measured', solver=info, metrics=metrics,
            residual_certificate=residual_cert, representer_certificate=repr_cert,
            solver_qualified=bool(info['converged'] and residual_cert['additional_gap_gate_passed'] and repr_cert['additional_gap_gate_passed']),
            fidelity_qualified=bool(metrics['target_wave_NRMSE'] < .02 and max(metrics['target_supported_band_complex_NRMSE']) < .02),
            old_results=old['metrics'], old_solver=old['solver'], old_certificate=old['certificate'],
            only_one_attempt=True, capture_sha256=sha(a.out/'capture.npz'), solve_wall_seconds=elapsed,
            source_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], 'solver', r['solver_qualified'], 'fidelity', r['fidelity_qualified'], flush=True)
        print(info, metrics, residual_cert, repr_cert, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
