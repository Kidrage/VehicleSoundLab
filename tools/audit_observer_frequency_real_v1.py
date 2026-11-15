"""Follow one source process and audit all30 source reconstructions independently."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--follow-pid', type=int)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.follow import Follow
    from observer_complete_v1.audit_capture import compare
    from observer_frequency_v1.audit_oracle import metric, objective_gradient
    from observer_complete_v1.audit_oracle import curvature, full_frame
    from observer_inverse_v1.audit_oracle import render_groups, observe
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    helpers = ('tools/observer_frequency_v1/audit_oracle.py', 'tools/observer_complete_v1/audit_oracle.py',
        'tools/observer_complete_v1/follow.py', 'tools/observer_complete_v1/audit_capture.py',
        'tools/observer_inverse_v1/audit_oracle.py', 'tools/circular_phase_lift_v1/audit_oracle.py')
    for j, name in enumerate(helpers): shutil.copy2(repo/name, a.out/f'executed_oracle_{j}.py')
    r = dict(result='running', pid=os.getpid(), cases=[], captures=0, band_Gram_matrices=0,
        maximum_wave_error=0., maximum_errors={})
    follow = Follow(a.study/'report.json', a.follow_pid)
    try:
        producer = follow.read()
        for name, digest in producer['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        preparation = load(a.study/'metric_preparation.json')
        assert sha(a.study/'metric_preparation.json') == producer['metric_preparation_sha256']
        parent = a.workspace/'baselines/observer_complete_v1/evidence/real1'
        for i in range(6):
            producer, case = follow.case(i)
            label = case['label']; folder = a.study/label
            assert sha(folder/'source.npz') == case['source_sha256']
            assert sha(folder/'scale.npz') == case['scale_sha256']
            with np.load(folder/'source.npz') as z, np.load(parent/label/'source.npz') as old:
                assert z.files == old.files and all(np.array_equal(z[k], old[k]) for k in z.files)
                audio, target, positions = z['audio'], z['coefficients'], z['positions']
                measured = observe(audio[:, None, :], case['root_hz'], producer['bands'])
                compare(measured, z, r)
            with np.load(folder/'scale.npz') as z:
                amp = np.sqrt(np.mean(abs(target)**2, axis=(0, 2)))
                scale = np.maximum(amp, amp.max()*1e-6)[:, None]
                assert np.array_equal(scale, z['scale'])
            _, _, weights, power, bins = metric(audio, case['root_hz'])
            assert sha(folder/'metric.npz') == case['metric_sha256'] == preparation[i]['metric_sha256']
            with np.load(folder/'metric.npz') as z:
                assert np.max(abs(weights/z['weights']-1)) < 2e-12 and np.array_equal(bins, z['bands'])
                assert np.max(abs(power-z['band_power'])) < 2e-12*max(power.max(), 1e-24)
                assert float(z['floor_fraction']) == 1e-8
            D = curvature(positions); row = dict(label=label, variants={})
            for tag, desc in case['variants'].items():
                path = folder/desc['file']; assert sha(path) == desc['sha256']
                with np.load(path) as z:
                    grouped = render_groups(z['nodes'], positions, case['root_hz'], producer['carrier_edges'], len(audio))
                    err = float(abs(grouped-z['grouped_audio']).max()); assert err < 2e-10
                    r['maximum_wave_error'] = max(r['maximum_wave_error'], err)
                    assert np.array_equal(z['audio'], z['grouped_audio'].sum(axis=1))
                    measured = observe(z['grouped_audio'], case['root_hz'], producer['bands'])
                    compare(measured, z, r)
                    q = z['nodes']/scale[None]; d = D@q.reshape(len(q), -1)
                    spectrum, _ = full_frame(z['audio']-audio)
                    value = float(np.sum(abs(spectrum*weights[None, :, None])**2)+.001*np.sum(abs(d)**2)+.000001*np.sum(abs(q)**2))
                    assert abs(value-desc['weighted_objective']) < 2e-8*max(1, value)
                    if tag == 'weighted':
                        value2, stationarity = objective_gradient(z['nodes'], positions, scale, audio, weights)
                        assert abs(value-value2) < 2e-8*max(1, value)
                        assert abs(stationarity-case['solve']['relative_stationarity']) < 2e-9
                        assert case['solve']['converged'] == bool(case['solve']['stop'] in (1, 2, 4, 5) and stationarity < 2e-7)
                        row['stationarity'] = stationarity
                    row['variants'][tag] = dict(weighted_objective=value, wave_NRMSE=float(z['wave_NRMSE']))
                r['captures'] += 1
                print('AUDITED frequency source', label, tag, flush=True)
            r['cases'].append(row); save(a.out/'report.json', r)
        producer = follow.read(); assert producer['result'] == 'observer_frequency_all6_measured'
        for path, digest in producer['inputs'].items(): assert sha(path) == digest
        assert r['captures'] == 30 and r['band_Gram_matrices'] == 14400
        r.update(result='independent_observer_frequency_real_passed', all_converged=producer['all_converged'],
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo/n) for n in helpers}, not_stochastic_source_or_timbre_qualification=True)
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise
    finally:
        follow.close()


if __name__ == '__main__':
    main()
