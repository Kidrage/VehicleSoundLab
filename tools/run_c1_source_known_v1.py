"""Known-first explicit C1 source packets with unchanged complete fit backend."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_source_adapter_v1.contract import prepare
    from c1_source_adapter_v1.objective import build
    from c1_source_adapter_v1.fixtures import cases
    from c1_source_adapter_v1.solve import solve
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, cases=[], material_read=False, block=64)
    try:
        previous_path = a.workspace/'references/analysis/locked_source_fit_v1/known1/report.json'
        previous = load(previous_path); r['inputs'][str(previous_path)] = sha(previous_path)
        assert previous['result'] == 'locked_source_fit_known_measured' and previous['all_qualified']
        bridge = a.workspace/'references/analysis/clock_native_bridge_v1/known_audit1/report.json'
        proof = load(bridge); r['inputs'][str(bridge)] = sha(bridge)
        assert proof['verification_passed'] and proof['all_known_qualified']
        names = set(previous['sources']) | {'tools/run_c1_source_known_v1.py', 'tools/audit_c1_source_known_v1.py',
            'research/c1_source_adapter_v1_plan.json'}
        for folder in ('c1_source_adapter_v1', 'clock_c1_v1'):
            names.update(v.relative_to(repo).as_posix() for v in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            if name in previous['sources']: assert sha(repo/name) == previous['sources'][name]
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for fixture in cases():
            label = fixture['label']; directory = a.out/label; directory.mkdir()
            r['current_case'] = label; save(a.out/'report.json', r)
            z, metadata = prepare(fixture['legacy'], fixture['observations'], fixture['clock'],
                fixture['new_audio'], fixture['taps'], fixture['cutoff'])
            system, shared, reference = build(z)
            rng = np.random.default_rng(94115)
            q = rng.normal(0, .2, system.nsize); rows = rng.normal(0, .1, system.shape[0])
            metric = system.metric; forward = system@q
            z.update(source_frequency=fixture['frequency'], source_coefficients=fixture['coefficients'],
                probe_q=q, probe_rows=rows, probe_forward=forward, probe_adjoint=system.rmatvec(rows),
                probe_normal=system.rmatvec(forward), probe_rhs=system.rhs(z['audio']),
                time_coverage=metric.time_coverage, coverage=metric.frame.coverage, target_slots=metric.target_window_slots)
            arrays, info = solve(system, shared, reference, z['audio'], directory)
            z.update(arrays)
            if label in ('nonlinear_zero', 'nonlinear_silent_right'):
                assert not np.count_nonzero(z['wave'][:, 1]) and not np.count_nonzero(z['q'][:, 1])
            np.savez_compressed(directory/'capture.npz', **z)
            info.update(result='c1_source_known_case_measured', label=label, metadata=metadata,
                file=label+'/capture.npz', capture_sha256=sha(directory/'capture.npz'),
                frames=len(z['audio']), nodes=len(z['positions']), orders=len(z['orders']), block=64,
                source_vs_legacy_wave_NRMSE=(float(np.linalg.norm(z['audio']-z['legacy_audio'])/np.linalg.norm(z['legacy_audio']))
                    if np.count_nonzero(z['legacy_audio']) else 0.))
            save(directory/'report.json', info)
            r['cases'].append(dict(label=label, file=info['file'], capture_sha256=info['capture_sha256'],
                report=label+'/report.json', report_sha256=sha(directory/'report.json'),
                solver_qualified=info['solver_qualified'], fidelity_qualified=info['fidelity_qualified']))
            save(a.out/'report.json', r)
            print('C1_SOURCE_KNOWN', label, info['solver_qualified'], info['fidelity_qualified'], flush=True)
            del z, arrays, system, shared, reference, info
            gc.collect()
        # Invalid contracts do not perform solves, alter the backend, or become material cases.
        f = next(cases()); invalid = []; reasons = {}
        def call(legacy=None, observations=None, clock=None, audio=None, taps=None, cutoff=None):
            packet, _ = prepare(f['legacy'] if legacy is None else legacy,
                f['observations'] if observations is None else observations,
                f['clock'] if clock is None else clock, f['new_audio'] if audio is None else audio,
                f['taps'] if taps is None else taps, f['cutoff'] if cutoff is None else cutoff)
            return build(packet)
        bad_clock = {k:v.copy() for k,v in f['clock'].items()}; bad_clock['coefficients'][0, 0] += 1e-6
        bad_observations = {k:v.copy() for k,v in f['observations'].items()}; bad_observations['y'][1] += 1e-6
        old = f['legacy']
        for name, args in (
            ('missing_metric_target', dict(legacy={k:v for k,v in old.items() if k!='metric_target'})),
            ('short_metric_target', dict(legacy=dict(old, metric_target=old['metric_target'][:-1]))),
            ('changed_legacy_target', dict(legacy=dict(old, target=old['target']*.99))),
            ('changed_old_source_target', dict(legacy=dict(old, target_source_coordinates=old['target_source_coordinates']+1e-5))),
            ('reversed_old_source', dict(legacy=dict(old, source_coordinates=old['source_coordinates'][::-1]))),
            ('changed_legacy_weights', dict(legacy=dict(old, weights=old['weights']*.99))),
            ('changed_sigma', dict(legacy=dict(old, sigma=old['sigma']*.99))),
            ('changed_scale', dict(legacy=dict(old, scale=-old['scale']))),
            ('changed_clock_coefficients', dict(clock=bad_clock)),
            ('moved_observation', dict(observations=bad_observations)),
            ('nonfinite_audio', dict(audio=f['new_audio']*np.nan)),
            ('complex_audio', dict(audio=f['new_audio'].astype(complex))),
            ('nonfinite_FIR', dict(taps=f['taps']*np.nan)),
            ('asymmetric_FIR', dict(taps=np.r_[f['taps'][:-1], 1.])),
            ('above_native_Nyquist', dict(cutoff=25000.)),
            ('above_grid_guard', dict(clock={k:(v*8 if k in ('y', 'origin', 'coefficients', 'interval_minimum_derivative') else v) for k,v in f['clock'].items()},
                observations=dict(x=f['observations']['x'], y=f['observations']['y']*8)))):
            try: call(**args)
            except (ValueError, TypeError) as error:
                invalid.append(name); reasons[name] = str(error)
                if name == 'above_grid_guard': assert 'slowest phase-grid' in str(error)
            else: raise AssertionError('Invalid source contract accepted: '+name)
        packet, _ = prepare(f['legacy'], f['observations'], f['clock'], f['new_audio'], f['taps'], f['cutoff'])
        saved = {k:v.copy() for k,v in packet.items()}
        for group in (f['legacy'], f['observations'], f['clock']):
            for value in group.values(): value[...] = 0
        f['new_audio'][:] = 0; f['taps'][:] = 0
        assert all(np.array_equal(value, saved[key]) for key,value in packet.items())
        r.update(result='c1_source_known_measured', invalid_rejections=invalid, invalid_rejection_reasons=reasons, owned_copy_check=True,
            all_qualified=all(c['solver_qualified'] and c['fidelity_qualified'] for c in r['cases']),
            no_actual_material_or_runtime_or_hearing_change=True)
        save(a.out/'report.json', r); print('C1_SOURCE_KNOWN_COMPLETE', r['all_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
