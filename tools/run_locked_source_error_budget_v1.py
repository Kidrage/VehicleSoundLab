"""Four-component signed diagnosis of one explicitly changed-source capture.

Reuse qualified unchanged interpolation/Gram equations. No source refit,
target replacement, original failed-report edits or sustained-source promotion.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'known-study', 'source-study', 'source-audit', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from native_error_budget_v1.interpolate import reconstruct
    from native_error_budget_v1.budget import analyze
    from locked_source_diagnostics_v1.native_input import bind
    from native_clock_render_v1.geometry import dense_query
    from native_clock_render_v1.filter import taps
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, variants=[])
    try:
        names = {'tools/run_locked_source_error_budget_v1.py', 'tools/audit_locked_source_error_budget_v1.py',
                 'research/locked_source_error_v1_plan.json', 'tools/research_archive_v1.py'}
        for folder in ('native_error_budget_v1', 'native_clock_render_v1', 'native_clock_case_v1',
                       'locked_source_diagnostics_v1', 'extraction_sound_v1'):
            names.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        known = load(a.known_study/'report.json')
        assert known['result'] == 'native_error_budget_known_qualified' and known['all_known_qualified']
        assert known['known']['all_qualified']
        for name in ('tools/native_error_budget_v1/interpolate.py', 'tools/native_error_budget_v1/budget.py',
                     'tools/native_error_budget_v1/known.py'):
            assert sha(repo/name) == sha(a.known_study/'exact_sources'/name) == known['sources'][name]
        native = load(a.source_study/'report.json')
        audit = load(a.source_audit/'report.json')
        assert native['result'] == 'locked_source_native_case_measured'
        assert audit['result'] == 'independent_locked_source_native_verified' and audit['verification_passed']
        assert audit['producer_sha256'] == sha(a.source_study/'report.json')
        args = native['paths']
        z, prepared, binding = bind(args['case'], args['math_audit'], repo=repo, workspace=a.workspace,
            native_study=args['native_study'], native_audit=args['native_audit'],
            known_study=args['known_study'], known_audit=args['known_audit'])
        r['inputs'].update(binding['inputs'])
        for path in (a.known_study/'report.json', a.source_study/'report.json', a.source_audit/'report.json'):
            r['inputs'][str(path)] = sha(path)
        raw, fir = prepared['raw_native_target'], prepared['source_FIR_only_target']
        signals = np.column_stack((z['audio'], z['wave']))
        for radius, up in ((32, 16), (64, 16), (128, 16), (128, 32)):
            path = a.source_study/('render'+str(up)+'.npz')
            r['inputs'][str(path)] = sha(path)
            assert sha(path) == next(c for c in native['renders'] if c['up'] == up)['sha256']
            with np.load(path) as f:
                continuous, query, kernel = f['native'], f['query'], f['taps']
            independent_query, _, _ = dense_query(z['source_coordinates'], float(prepared['native_start']),
                                                  len(raw), up=up, delay=128*up)
            assert np.array_equal(query, independent_query) and np.array_equal(kernel, taps(up))
            dense = reconstruct(signals, query, radius)
            rendered = signal.fftconvolve(dense, kernel[:, None], mode='valid', axes=0)[::up]
            phase, fit_grid = rendered[:, :2], rendered[:, 2:]
            arrays, info = analyze(raw, fir, phase, fit_grid, continuous)
            filename = 'radius'+str(radius)+'_up'+str(up)+'.npz'
            output = a.out/filename
            np.savez_compressed(output, raw=raw, FIR_only=fir, phase_reconstruction=phase,
                fitted_grid_reconstruction=fit_grid, continuous_OSC=continuous, **arrays)
            r['variants'].append(dict(radius=radius, up=up, file=filename, sha256=sha(output), **info))
            save(a.out/'report.json', r)
            print('LOCKED_SOURCE_ERROR_VARIANT', radius, up, info['closure_max_FS'], flush=True)
        r.update(result='locked_source_native_error_budget_measured', source=binding['source'],
            native_study=str(a.source_study), native_audit=str(a.source_audit),
            source_solver_qualified=native['source_solver_qualified'],
            source_fidelity_qualified=native['source_fidelity_qualified'],
            native16_32_convergence_passed=native['native16_32_convergence_passed'],
            eligible_for_later_source_statistics=native['eligible_for_later_source_statistics'],
            locked_band_power=z['band_power'].tolist(), locked_floor_active=z['floor_active'].tolist(),
            locked_sigma=float(z['sigma']), locked_amplitude=float(z['amplitude']),
            original_source_metrics=load(Path(args['case'])/'report.json')['metrics'],
            original_native_comparisons=native['comparisons'],
            explicit_new_audio_and_unchanged_legacy_metric_target=True,
            original_failures_and_all_gates_retained=True,
            reused_unchanged_known_core=str(a.known_study/'report.json'),
            no_refit_or_gate_change_or_source_promotion=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
