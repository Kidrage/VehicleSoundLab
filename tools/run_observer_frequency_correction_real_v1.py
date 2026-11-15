"""One saved-solution correction on every original source, unchanged objective."""
import argparse, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'known-audit', 'original', 'original-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem
    from observer_frequency_v1.correction import correct
    from observer_inverse_v1.diagnostics import capture
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={},
        in_sample_only=True, unchanged_objective=True, one_correction_per_source=True)
    print('FREQUENCY_CORRECTION_PID', os.getpid(), flush=True)
    try:
        known, audit = load(a.known/'report.json'), load(a.known_audit/'report.json')
        assert known['result'] == 'observer_frequency_correction_known_ready'
        assert audit['result'] == 'independent_observer_frequency_correction_known_passed'
        assert audit['producer_sha256'] == sha(a.known/'report.json')
        assert audit['auditor_sha256'] == sha(repo/'tools/audit_observer_frequency_correction_known_v1.py')
        for name, digest in known['sources'].items(): assert sha(repo/name) == digest
        old, old_audit = load(a.original/'report.json'), load(a.original_audit/'report.json')
        assert old['result'] == 'observer_frequency_all6_measured' and len(old['cases']) == 6
        assert old_audit['result'] == 'independent_observer_frequency_real_passed'
        assert old_audit['producer_sha256'] == sha(a.original/'report.json')
        for name, digest in old['sources'].items(): assert sha(repo/name) == digest
        names = tuple(set(known['sources']) | set(old['sources']) | {
            'tools/run_observer_frequency_correction_real_v1.py', 'tools/observer_inverse_v1/diagnostics.py'})
        for name in sorted(names):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        def consume(path): r['inputs'][str(path)] = sha(path); return path
        for path in (a.known/'report.json', a.known_audit/'report.json', a.original/'report.json',
                     a.original_audit/'report.json', a.original/'metric_preparation.json'):
            consume(path)
        assert sha(a.original/'metric_preparation.json') == old['metric_preparation_sha256']
        r.update(bands=old['bands'], carrier_edges=old['carrier_edges'])
        preparation = []
        for case in old['cases']:
            folder = a.out/case['label']; folder.mkdir()
            for name, digest, dest_name in (
                ('source.npz', case['source_sha256'], 'source.npz'),
                ('scale.npz', case['scale_sha256'], 'scale.npz'),
                ('metric.npz', case['metric_sha256'], 'metric.npz'),
                (case['variants']['weighted']['file'], case['variants']['weighted']['sha256'], 'initial.npz')):
                path = consume(a.original/case['label']/name); assert sha(path) == digest
                shutil.copy2(path, folder/dest_name)
            preparation.append(dict(label=case['label'], files={n: sha(folder/n)
                for n in ('source.npz', 'scale.npz', 'metric.npz', 'initial.npz')}))
        save(a.out/'preparation.json', preparation); r['preparation_sha256'] = sha(a.out/'preparation.json')
        save(a.out/'report.json', r)
        for case in old['cases']:
            label = case['label']; folder = a.out/label
            with np.load(folder/'source.npz') as z:
                audio, target, positions = z['audio'], z['coefficients'], z['positions']
            with np.load(folder/'scale.npz') as z: scale = z['scale']
            with np.load(folder/'initial.npz') as z: initial = z['nodes']
            synthesis = WaveSynthesis(len(audio), positions, np.arange(1, 289))
            metric = FrequencyMetric(audio, case['root_hz'])
            with np.load(folder/'metric.npz') as z:
                assert np.array_equal(metric.weights, z['weights'])
                assert np.array_equal(metric.band_power, z['band_power'])
            system = WeightedSystem(synthesis, scale, metric)
            print('FREQUENCY CORRECTION START', label, flush=True); start = time.perf_counter()
            nodes, info, right = correct(system, audio, initial)
            info['elapsed_host_seconds_not_SHARC_cycles'] = time.perf_counter()-start
            info['previous_iterations'] = case['solve']['iterations']
            info['cumulative_iterations'] = info['previous_iterations']+info['iterations']
            assert np.isclose(info['initial_objective'], case['solve']['objective'], rtol=1e-8, atol=1e-10)
            assert np.isclose(info['initial_relative_stationarity'], case['solve']['relative_stationarity'], rtol=1e-7, atol=1e-12)
            path = folder/'right.npz'; np.savez_compressed(path, matrix=right.matrix)
            values = capture(synthesis, nodes, case['root_hz'], r['bands'], r['carrier_edges'], audio, target)
            dest = folder/'block_refined.npz'; np.savez_compressed(dest, **values)
            row = dict(label=label, root_hz=case['root_hz'], frames=len(audio), source_rows=case['source_rows'],
                source_sha256=sha(folder/'source.npz'), scale_sha256=sha(folder/'scale.npz'),
                metric_sha256=sha(folder/'metric.npz'), initial_sha256=sha(folder/'initial.npz'),
                file=dest.name, sha256=sha(dest), right_sha256=sha(path), solve=info)
            r['cases'].append(row); save(a.out/'report.json', r)
            print('FREQUENCY CORRECTION DONE', label, info['stop'], info['iterations'],
                info['relative_stationarity'], 'wave', float(values['wave_NRMSE']), flush=True)
        r.update(result='observer_frequency_correction_all6_measured',
            all_converged=all(c['solve']['converged'] for c in r['cases']),
            new_stochastic_source=False, native48k_or_C_or_hearing=False)
        save(a.out/'report.json', r); print(r['result'], 'all_converged', r['all_converged'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
