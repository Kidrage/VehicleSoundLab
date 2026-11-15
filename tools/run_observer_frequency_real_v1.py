"""One known-qualified complete shared-frequency rule, all6 frozen source records."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'known-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem, infer
    from observer_inverse_v1.fit import real_vector
    from observer_inverse_v1.diagnostics import capture
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={}, in_sample_only=True)
    print('FREQUENCY_SOURCE_PID', os.getpid(), flush=True)
    try:
        known, audit = load(a.known/'report.json'), load(a.known_audit/'report.json')
        assert known['result'] == 'observer_frequency_known_ready'
        assert audit['result'] == 'independent_observer_frequency_known_passed'
        assert audit['producer_sha256'] == sha(a.known/'report.json')
        assert audit['auditor_sha256'] == sha(repo/'tools/audit_observer_frequency_known_v1.py')
        for name, digest in known['sources'].items():
            assert sha(repo/name) == sha(a.known/'exact_sources'/name) == digest
        names = tuple(known['sources'])+('tools/run_observer_frequency_real_v1.py',
            'research/observer_frequency_metric_v1_plan.json', 'tools/observer_inverse_v1/diagnostics.py',
            'tools/conditional_phase_time_v1/observer.py', 'tools/carrier_transfer_v1/spectral.py',
            'tools/carrier_transfer_v1/groups.py', 'tools/sound_dna/windowed.py')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        def consume(path): r['inputs'][str(path)] = sha(path); return path
        for path in (a.known/'report.json', a.known_audit/'report.json'): consume(path)
        parent = a.workspace/'baselines/observer_complete_v1'
        assert sha(parent/'manifest.json') == load(repo/'research/observer_complete_v1_summary.json')['manifest_sha256']
        entries = {row['path']: row['sha256'] for row in load(parent/'manifest.json')['files']}
        def frozen(name):
            path = parent/name; assert sha(path) == entries[name]; return consume(path)
        old = load(frozen('evidence/real1/report.json'))
        r.update(parent_manifest_sha256=sha(parent/'manifest.json'), bands=old['bands'], carrier_edges=old['carrier_edges'])
        preparation = []
        # Calculate and bind the single metric for ALL sources before any fit.
        for case in old['cases']:
            folder = a.out/case['label']; folder.mkdir()
            for name in ('source.npz', 'scale.npz'):
                shutil.copy2(frozen('evidence/real1/'+case['label']+'/'+name), folder/name)
            with np.load(folder/'source.npz') as z:
                met = FrequencyMetric(z['audio'], case['root_hz'])
            path = folder/'metric.npz'
            np.savez_compressed(path, weights=met.weights, band_power=met.band_power,
                global_power=met.global_power, bands=met.bands, floor_fraction=met.floor_fraction)
            preparation.append(dict(label=case['label'], metric_sha256=sha(path),
                joint_band_record_power=met.band_power.tolist(), global_record_power=met.global_power,
                weight_range=[float(met.weights.min()), float(met.weights.max())],
                floor_fraction=met.floor_fraction, all_bins_retained=True, shared_LR=True))
        save(a.out/'metric_preparation.json', preparation)
        r['metric_preparation_sha256'] = sha(a.out/'metric_preparation.json')
        save(a.out/'report.json', r)
        for j, case in enumerate(old['cases']):
            label = case['label']; folder = a.out/label
            with np.load(folder/'source.npz') as z:
                audio, target, positions = z['audio'], z['coefficients'], z['positions']
            with np.load(folder/'scale.npz') as z: scale = z['scale']
            synthesis = WaveSynthesis(len(audio), positions, np.arange(1, 289))
            met = FrequencyMetric(audio, case['root_hz'])
            with np.load(folder/'metric.npz') as z: assert np.array_equal(met.weights, z['weights'])
            system = WeightedSystem(synthesis, scale, met); rhs = system.rhs(audio)
            row = dict(label=label, root_hz=case['root_hz'], frames=len(audio), source_rows=case['source_rows'],
                source_sha256=sha(folder/'source.npz'), scale_sha256=sha(folder/'scale.npz'),
                metric_sha256=sha(folder/'metric.npz'), variants={})
            for tag, desc in case['variants'].items():
                path = frozen('evidence/real1/'+label+'/'+desc['file'])
                assert sha(path) == desc['sha256']
                dest = folder/(tag+'.npz'); shutil.copy2(path, dest)
                with np.load(dest) as z:
                    residual = system@real_vector(z['nodes']/scale[None])-rhs
                    objective = float(residual@residual)
                row['variants'][tag] = dict(file=dest.name, sha256=sha(dest), weighted_objective=objective)
            print('FREQUENCY FIT START', label, flush=True)
            nodes, info, right = infer(synthesis, audio, scale, met)
            np.savez_compressed(folder/'right.npz', time=right.time, real_scale=right.real_scale, imag_scale=right.imag_scale)
            values = capture(synthesis, nodes, case['root_hz'], r['bands'], r['carrier_edges'], audio, target)
            path = folder/'weighted.npz'; np.savez_compressed(path, **values)
            row['variants']['weighted'] = dict(file=path.name, sha256=sha(path), weighted_objective=info['objective'])
            row.update(solve=info, right_sha256=sha(folder/'right.npz'))
            assert info['objective'] <= row['variants']['interpolated']['weighted_objective']*(1+1e-10)
            r['cases'].append(row); save(a.out/'report.json', r)
            print('FREQUENCY FIT DONE', label, info['stop'], info['iterations'], info['relative_stationarity'],
                'wave', float(values['wave_NRMSE']), flush=True)
        r.update(result='observer_frequency_all6_measured', all_converged=all(c['solve']['converged'] for c in r['cases']),
            new_stochastic_source=False, native48k_or_C_or_hearing=False)
        save(a.out/'report.json', r); print(r['result'], 'all_converged', r['all_converged'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
