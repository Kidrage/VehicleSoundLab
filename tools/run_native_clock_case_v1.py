"""Render one audited actual full288 case at16x/32x; never start extraction."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'case', 'math-audit', 'native-study', 'native-audit',
                 'known-study', 'known-audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    from native_clock_case_v1.binding import bind
    from native_clock_case_v1.diagnostics import comparison, convergence
    from native_clock_render_v1.filter import render
    from extraction_sound_v1.measure import measure
    from extraction_sound_v1.consume import precision
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', label=a.case.name, sources={}, inputs={}, renders=[], comparisons={})
    try:
        names = {'tools/run_native_clock_case_v1.py', 'tools/audit_native_clock_case_v1.py',
                 'research/native_clock_case_v1_plan.json', 'tools/research_archive_v1.py'}
        for folder in ('native_clock_case_v1', 'native_clock_render_v1', 'extraction_sound_v1',
                       'native_clock_case_audit_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo / 'tools' / folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest)
            r['sources'][name] = sha(dest)
        plan = load(repo / 'research/native_clock_case_v1_plan.json')
        z, native, binding = bind(a.case, a.math_audit, repo=repo, workspace=a.workspace,
            native_study=a.native_study, native_audit=a.native_audit,
            known_study=a.known_study, known_audit=a.known_audit)
        r.update(binding)
        r['paths'] = {name: str(getattr(a, name)) for name in
                      ('case', 'math_audit', 'native_study', 'native_audit', 'known_study', 'known_audit')}
        r['gates'] = plan['gates']
        count = len(native['raw_native_target'])
        audio = dict(raw=native['raw_native_target'], FIR_only=native['source_FIR_only_target'])
        for up in (16, 32):
            arrays, info = render(z['fitted'], z['positions'], z['orders'], z['source_coordinates'],
                                 float(native['native_start']), count, up=up)
            if not np.array_equal(arrays['query'], native['query' + str(up)]):
                raise ValueError('Renderer query differs from independently prepared physical interval')
            output = a.out / ('render' + str(up) + '.npz')
            np.savez_compressed(output, **arrays)
            r['renders'].append(dict(up=up, file=output.name, sha256=sha(output), geometry=info))
            audio['fitted' + str(up)] = arrays['native']
            save(a.out / 'report.json', r)
            print('ACTUAL_NATIVE_RENDER', a.case.name, up, count, flush=True)
            del arrays
        measurements = {name: measure(value, 48000) for name, value in audio.items()}
        output = a.out / 'sound.npz'
        np.savez_compressed(output, **{name + '_audio': value for name, value in audio.items()},
            **{name + '_' + key: value for name, result in measurements.items() for key, value in result.items()})
        r['sound'] = dict(file=output.name, sha256=sha(output), rate=48000, frames=count,
                         precision={name: precision(result) for name, result in measurements.items()})
        for candidate, reference in (('fitted16', 'raw'), ('fitted32', 'raw'),
                                     ('fitted16', 'FIR_only'), ('fitted32', 'FIR_only'),
                                     ('fitted16', 'fitted32'), ('FIR_only', 'raw')):
            r['comparisons'][candidate + '_vs_' + reference] = comparison(
                audio[candidate], audio[reference], measurements[candidate], measurements[reference])
        passed = convergence(r['comparisons']['fitted16_vs_fitted32'], plan['gates'])
        r.update(result='actual_native_clock_case_measured', native16_32_convergence_passed=passed,
            source_solver_qualified=binding['source']['solver_qualified'],
            source_fidelity_qualified=binding['source']['fidelity_qualified'],
            eligible_for_later_source_statistics=bool(passed and binding['source']['solver_qualified']
                                                     and binding['source']['fidelity_qualified']),
            no_gain_matching_or_time_alignment=True, all_original288_orders_and_nodes=True,
            fitted_trajectories_are_diagnostics_never_loops=True,
            source_FIR_only_is_not_complete_upstream_interpolator_inverse=True,
            no_C_or_default_or_hearing_or_sustained_source_promotion=True)
        save(a.out / 'report.json', r)
        print('ACTUAL_NATIVE_COMPLETE', a.case.name, 'convergence', passed,
              'solver', binding['source']['solver_qualified'],
              'fidelity', binding['source']['fidelity_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out / 'report.json', r)
        raise


if __name__ == '__main__':
    main()
