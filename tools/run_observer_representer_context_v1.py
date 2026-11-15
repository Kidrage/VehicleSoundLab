"""Eight unchanged original-Hann context fixtures after independent finite controls."""
import argparse, os, shutil, sys
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
    from observer_representer_v1.primal import infer
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={}, material_read=False)
    try:
        parent, audit = load(a.original/'report.json'), load(a.prerequisite/'report.json')
        assert parent['result'] == 'observer_context_known_measured'
        assert audit['result'] == 'independent_observer_representer_algebra_passed' and audit['all_qualified']
        for path in (a.original/'report.json', a.prerequisite/'report.json'):
            r['inputs'][str(path)] = sha(path)
        names = tuple(parent['sources'])+('tools/run_observer_representer_context_v1.py',
            'tools/observer_representer_v1/dual.py', 'tools/observer_representer_v1/primal.py',
            'research/observer_representer_primal_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        print('REPRESENTER_CONTEXT_PID', os.getpid(), flush=True)
        for old in parent['cases']:
            path = a.original/old['file']
            assert sha(path) == old['sha256']
            r['inputs'][str(path)] = sha(path)
            with np.load(path) as z:
                audio, positions, orders, scale = (z[n] for n in ('audio', 'positions', 'orders', 'scale'))
                original, truth = z['dense_nodes'], z['source_nodes']
            synthesis = WaveSynthesis(len(audio), positions, orders, audio.shape[1])
            metric = SupportedMetric(audio, 64.)
            system = SupportedSystem(synthesis, scale, metric)
            fitted, u, info, residual_cert, repr_cert = infer(system, audio, maxiter=4000)
            relative = float(np.linalg.norm((fitted-original)/scale[None])/np.linalg.norm(original/scale[None]))
            wave, target = synthesis.synthesize(fitted), synthesis.synthesize(truth)
            high = np.array([0., 1.])[None, :, None]
            hd, ht = synthesis.synthesize(fitted*high), synthesis.synthesize(truth*high)
            crop = slice(2176, 6529)
            metrics = dict(whole_wave_NRMSE=float(np.linalg.norm(wave-target)/np.linalg.norm(target)),
                target_wave_NRMSE=float(np.linalg.norm((wave-target)[crop])/np.linalg.norm(target[crop])),
                whole_high_NRMSE=float(np.linalg.norm(hd-ht)/np.linalg.norm(ht)),
                target_high_NRMSE=float(np.linalg.norm((hd-ht)[crop])/np.linalg.norm(ht[crop])))
            qualified = bool(relative < 2e-7 and info['converged'] and
                residual_cert['additional_gap_gate_passed'] and repr_cert['additional_gap_gate_passed'])
            dest = a.out/old['file']
            np.savez_compressed(dest, audio=audio, positions=positions, orders=orders, scale=scale,
                source_nodes=truth, original_dense_nodes=original, fitted=fitted, u=u,
                weights=metric.weights, band_power=metric.band_power, floor_active=metric.floor_active)
            r['cases'].append(dict(label=old['label'], file=dest.name, sha256=sha(dest), solver=info,
                dense_relative_error=relative, metrics=metrics, residual_certificate=residual_cert,
                representer_certificate=repr_cert, qualified=qualified, original_outer_loss_not_reclassified=True))
            save(a.out/'report.json', r)
            print('ORIGINAL METRIC', old['label'], qualified, relative, info['stop'], info['iterations'], metrics, flush=True)
        r.update(result='observer_representer_context_measured', all_qualified=all(c['qualified'] for c in r['cases']),
            full288_or_material_or_runtime_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
