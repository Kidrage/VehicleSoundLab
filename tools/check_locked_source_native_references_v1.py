"""Exercise the reference bridge on all five actual preparations, without a fit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_diagnostics_v1.native_reference import bind_reference
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], inputs={}, sources={})
    try:
        names = {'tools/check_locked_source_native_references_v1.py', 'research/locked_source_diagnostics_v1_plan.json',
            'tools/locked_source_diagnostics_v1/native_reference.py', 'tools/extraction_sound_v1/consume.py',
            'tools/research_archive_v1.py'}
        for name in sorted(names):
            dest = args.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); report['sources'][name] = sha(dest)
        root = args.workspace/'references/analysis/locked_source_fit_v1'
        native = args.workspace/'references/analysis/native_clock_render_v1'
        source, audit = load(root/'prepare1/report.json'), load(root/'prepare_audit1/report.json')
        assert source['result'] == 'locked_source_five_prepared' and audit['all_qualified']
        assert audit['producer_sha256'] == sha(root/'prepare1/report.json') and len(audit['cases']) == 5
        for directory in ('prepare1', 'prepare_audit1'):
            path = root/directory/'report.json'; report['inputs'][str(path)] = sha(path)
        for row in source['cases']:
            path = root/'prepare1'/row['file']; assert sha(path) == row['sha256']
            with np.load(path) as saved: z = {name: saved[name] for name in saved.files}
            observed, binding = bind_reference(z, row['label'], path, row['sha256'], repo=repo, workspace=args.workspace,
                native_study=native/'prepare1', native_audit=native/'prepare_audit1',
                known_study=native/'known1', known_audit=native/'known_audit1')
            report['inputs'].update(binding['inputs'])
            # Independent complete inverse-clock arithmetic, not the renderer.
            q = z['source_coordinates']; origin = float(q[0]); relative = q-origin
            count = len(observed['raw_native_target']); errors = {}
            for up in (16, 32):
                ticks = np.arange(-128*up, (count-1)*up+128*up+1)
                t = float(observed['native_start'])-origin+ticks/(48000*up)
                assert t[0] >= 0 and t[-1] <= relative[-1]
                index = np.searchsorted(relative, t, side='right')-1
                index[index == len(relative)-1] = len(relative)-2
                expected = index+(t-relative[index])/(relative[index+1]-relative[index])
                difference = float(np.max(abs(expected-observed['query'+str(up)]))/1024)
                assert difference <= 2e-12
                errors[str(up)] = difference
            first, stop = int(observed['first']), int(observed['stop'])
            assert np.array_equal(observed['raw_native_target'], z['native'][first:stop])
            with np.load(row['original_preparation']) as old:
                assert np.array_equal(z['metric_target'], old['target'])
            assert binding['new_method_preparation'] == row
            report['cases'].append(dict(label=row['label'], all_reference_checks_passed=True,
                native_frames=count, inverse_cycle_max_errors=errors, orders=288,
                fitted_native_admission_exercised=False))
            save(args.out/'report.json', report)
            print('LOCKED_NATIVE_REFERENCE', row['label'], 'PASS', flush=True)
        report.update(result='locked_source_native_references_checked', all_reference_checks_passed=True,
            no_terminal_fit_admission_or_render_qualification=True, no_C_or_hearing_or_sustained_promotion=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
