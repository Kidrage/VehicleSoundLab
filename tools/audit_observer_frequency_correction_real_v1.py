"""Follow one correction process; independently audit initial and corrected waves."""
import argparse, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--follow-pid', type=int)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.follow import Follow
    from observer_complete_v1.audit_capture import compare
    from observer_frequency_v1.audit_oracle import metric, objective_gradient
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
        for name, digest in producer['sources'].items(): assert sha(repo/name) == sha(a.study/'exact_sources'/name) == digest
        preparation = load(a.study/'preparation.json')
        assert sha(a.study/'preparation.json') == producer['preparation_sha256']
        parent = a.workspace/'baselines/observer_complete_v1/evidence/real1'
        original = a.workspace/'references/analysis/observer_frequency_v1/real1'
        old_report = load(original/'report.json')
        for i in range(6):
            producer, case = follow.case(i)
            label = case['label']; folder = a.study/label
            for name, digest in preparation[i]['files'].items(): assert sha(folder/name) == digest
            assert sha(folder/'source.npz') == case['source_sha256'] == sha(parent/label/'source.npz')
            assert sha(folder/'scale.npz') == case['scale_sha256'] == sha(parent/label/'scale.npz')
            assert sha(folder/'initial.npz') == case['initial_sha256'] == old_report['cases'][i]['variants']['weighted']['sha256']
            with np.load(folder/'source.npz') as z:
                audio, target, positions = z['audio'], z['coefficients'], z['positions']
                compare(observe(audio[:, None, :], case['root_hz'], producer['bands']), z, r)
            with np.load(folder/'scale.npz') as z:
                amp = np.sqrt(np.mean(abs(target)**2, axis=(0, 2)))
                scale = np.maximum(amp, amp.max()*1e-6)[:, None]
                assert np.array_equal(scale, z['scale'])
            _, _, weights, power, bins = metric(audio, case['root_hz'])
            assert sha(folder/'metric.npz') == case['metric_sha256'] == sha(original/label/'metric.npz')
            with np.load(folder/'metric.npz') as z:
                assert np.max(abs(weights/z['weights']-1)) < 2e-12 and np.array_equal(bins, z['bands'])
                assert np.max(abs(power-z['band_power'])) < 2e-12*max(power.max(), 1e-24)
                assert float(z['floor_fraction']) == 1e-8
            with np.load(folder/'right.npz') as z:
                assert sha(folder/'right.npz') == case['right_sha256']
                assert z['matrix'].shape == (288, 2*len(positions), 2*len(positions)) and np.isfinite(z['matrix']).all()
            row = dict(label=label, variants={})
            for tag, name, digest, obj_key, g_key in (
                ('initial', 'initial.npz', case['initial_sha256'], 'initial_objective', 'initial_relative_stationarity'),
                ('block_refined', case['file'], case['sha256'], 'objective', 'relative_stationarity')):
                path = folder/name; assert sha(path) == digest
                with np.load(path) as z:
                    grouped = render_groups(z['nodes'], positions, case['root_hz'], producer['carrier_edges'], len(audio))
                    err = float(abs(grouped-z['grouped_audio']).max()); assert err < 2e-10
                    r['maximum_wave_error'] = max(r['maximum_wave_error'], err)
                    assert np.array_equal(z['audio'], z['grouped_audio'].sum(axis=1))
                    compare(observe(z['grouped_audio'], case['root_hz'], producer['bands']), z, r)
                    value, g = objective_gradient(z['nodes'], positions, scale, audio, weights)
                    assert abs(value-case['solve'][obj_key]) < 2e-8*max(1., value)
                    assert abs(g-case['solve'][g_key]) < 2e-9
                    row['variants'][tag] = dict(objective=value, relative_stationarity=g, wave_NRMSE=float(z['wave_NRMSE']))
                r['captures'] += 1
                print('AUDITED correction', label, tag, flush=True)
            info = case['solve']; g = row['variants']['block_refined']['relative_stationarity']
            assert info['converged'] == bool(info['stop'] in (1, 2, 4, 5) and g < 2e-7)
            assert info['same_weighted_objective'] and not info['equivalent_saved_right_map']
            assert info['alpha'] == .001 and info['beta'] == .000001
            assert info['previous_iterations'] == old_report['cases'][i]['solve']['iterations']
            assert info['cumulative_iterations'] == info['previous_iterations']+info['iterations']
            assert row['variants']['block_refined']['objective'] <= row['variants']['initial']['objective']*(1+2e-10)+1e-20
            r['cases'].append(row); save(a.out/'report.json', r)
        producer = follow.read()
        while producer['result'] == 'running' and follow.alive():
            time.sleep(.1); producer = follow.read()
        assert producer['result'] == 'observer_frequency_correction_all6_measured'
        for path, digest in producer['inputs'].items(): assert sha(path) == digest
        assert r['captures'] == 12 and r['band_Gram_matrices'] == 5760
        r.update(result='independent_observer_frequency_correction_real_passed', all_converged=producer['all_converged'],
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
            oracles_sha256={n: sha(repo/n) for n in helpers}, not_stochastic_source_or_timbre_qualification=True)
        save(a.out/'report.json', r); print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise
    finally:
        follow.close()


if __name__ == '__main__': main()
