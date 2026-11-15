"""All6 saved solutions, same full objective, bounded checkpointed correction."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'parent', 'known', 'known-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.fit import RegularizedObserver
    from observer_inverse_v1.refinement import SavedRightMap, refine
    from observer_inverse_v1.diagnostics import capture
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={},
        in_sample_only=True, max_correction_stages=3, max_iterations_per_stage=4000)
    print('CORRECTION_PID', os.getpid(), flush=True)
    try:
        known, audit = load(a.known/'report.json'), load(a.known_audit/'report.json')
        assert known['result'] == 'observer_inverse_refinement_known_ready'
        assert audit['result'] == 'independent_observer_inverse_refinement_known_passed'
        assert audit['producer_sha256'] == sha(a.known/'report.json')
        assert audit['auditor_sha256'] == sha(repo/'tools/audit_observer_inverse_refinement_known_v1.py')
        for name, digest in known['sources'].items():
            assert sha(repo/name) == sha(a.known/'exact_sources'/name) == digest
        names = ('research/observer_inverse_v1_plan.json',
            'tools/run_observer_inverse_refinement_real_v1.py',
            'tools/observer_forward_v1/operator.py', 'tools/observer_forward_v1/polyphase.py',
            'tools/observer_inverse_v1/fit.py', 'tools/observer_inverse_v1/regularizer.py',
            'tools/observer_inverse_v1/refinement.py', 'tools/observer_inverse_v1/diagnostics.py',
            'tools/conditional_phase_time_v1/observer.py', 'tools/carrier_transfer_v1/spectral.py',
            'tools/carrier_transfer_v1/groups.py', 'tools/sound_dna/windowed.py')
        for name in names:
            dest = a.out/'exact_sources'/name;dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest);r['sources'][name] = sha(dest)
        def consume(path):
            r['inputs'][str(path)] = sha(path)
            return path
        for path in (a.known/'report.json', a.known_audit/'report.json', a.parent/'report.json'):
            consume(path)
        old = load(a.parent/'report.json')
        assert old['result'] == 'observer_inverse_all6_measured' and len(old['cases']) == 6
        assert not old['all_converged']
        r.update(bands=old['bands'], carrier_edges=old['carrier_edges'],
            parent_sha256=sha(a.parent/'report.json'), known_sha256=sha(a.known/'report.json'),
            known_audit_sha256=sha(a.known_audit/'report.json'))
        save(a.out/'report.json', r)
        for case in old['cases']:
            label = case['label'];folder = a.out/label;folder.mkdir()
            before = a.parent/label
            for name, key in (('source.npz', 'source_sha256'), ('scale.npz', 'scale_sha256'),
                              ('precondition.npz', 'precondition_sha256')):
                assert sha(before/name) == case[key]
                shutil.copy2(consume(before/name), folder/name)
            with np.load(folder/'source.npz') as z:
                audio, target, positions = z['audio'], z['coefficients'], z['positions']
            with np.load(folder/'scale.npz') as z:
                scale = z['scale']
            op = PolyphaseObserver(len(audio), positions, np.arange(1, 289), np.arange(1, 289))
            system = RegularizedObserver(op, scale)
            with np.load(folder/'precondition.npz') as z:
                right = SavedRightMap(op.shape, z['time'], z['real_scale'], z['imag_scale'])
            desc = case['variants']['inverse'];path = before/desc['file']
            assert sha(path) == desc['sha256']
            with np.load(consume(path)) as z:
                nodes = z['nodes']
            row = dict(case);row['correction_stages'] = [];row['variants'] = {}
            row['parent_solve'] = case['solve']
            for stage in range(1, r['max_correction_stages']+1):
                print('CORRECTION START', label, stage, flush=True)
                nodes, info = refine(system, right, target, nodes,
                    maxiter=r['max_iterations_per_stage'])
                path = folder/f'correction_{stage}.npz'
                np.savez_compressed(path, nodes=nodes)
                row['correction_stages'].append(dict(stage=stage, file=path.name,
                    sha256=sha(path), **info))
                r['current_correction'] = dict(label=label, stages=row['correction_stages'])
                save(a.out/'report.json', r)
                print('CORRECTION DONE', label, stage, info['stop'], info['iterations'],
                    info['relative_stationarity'], flush=True)
                if info['converged']:
                    break
            row['solve'] = info
            row['cumulative_iterations'] = case['solve']['iterations']+sum(s['iterations'] for s in row['correction_stages'])
            desc = case['variants']['interpolated_observations'];path = before/desc['file']
            assert sha(path) == desc['sha256']
            shutil.copy2(consume(path), folder/path.name)
            row['variants']['interpolated_observations'] = desc
            values = capture(op, nodes, case['root_hz'], r['bands'], r['carrier_edges'], audio, target)
            path = folder/'inverse.npz';np.savez_compressed(path, **values)
            row['variants']['inverse'] = dict(file=path.name, sha256=sha(path),
                wave_NRMSE=float(values['wave_NRMSE']))
            r['cases'].append(row);r.pop('current_correction', None)
            save(a.out/'report.json', r)
        r.update(result='observer_inverse_all6_measured',
            all_converged=all(c['solve']['converged'] for c in r['cases']),
            new_stochastic_source=False, real_RPM_or_native48k_or_runtime_C_or_hearing=False)
        save(a.out/'report.json', r)
        print(r['result'], 'all_converged', r['all_converged'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error));save(a.out/'report.json', r);raise


if __name__ == '__main__':
    main()
