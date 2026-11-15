"""Consume audited new-method controls or one terminal real fit, without fitting."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'math-audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--known-check', action='store_true')
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    from locked_source_diagnostics_v1.input import terminal
    from locked_source_diagnostics_v1.virtual import consume

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', sources={}, cases=[], guard_rejections=[])
    try:
        names = {'tools/run_locked_source_virtual_v1.py', 'tools/audit_locked_source_virtual_v1.py',
                 'research/locked_source_diagnostics_v1_plan.json', 'tools/research_archive_v1.py',
                 'tools/native_clock_case_audit_v1/sound.py', 'research/native_clock_case_v1_plan.json'}
        for folder in ('locked_source_diagnostics_v1', 'extraction_sound_v1'):
            names.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest = args.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); report['sources'][name] = sha(dest)
        proof = load(args.math_audit)
        if args.known_check:
            assert proof['result'] == 'independent_locked_source_known_verified' and proof['all_qualified']
            cases = [args.study/row['label'] for row in proof['cases'] if row['complete_audit_file']]
            assert len(cases) == 3
        else: cases = [args.study]
        meter = args.workspace/'references/analysis/extraction_sound_v1'
        for case in cases:
            output = args.out/case.name
            result = consume(case, args.math_audit, output, repo=repo, meter_study=meter/'known2',
                meter_audit=meter/'known_composed_audit1', known=args.known_check)
            report['cases'].append(dict(label=case.name, report=case.name+'/report.json', sha256=sha(output/'report.json'),
                solver_qualified=result['source']['solver_qualified'], fidelity_qualified=result['source']['fidelity_qualified']))
            save(args.out/'report.json', report)
            print('LOCKED_VIRTUAL', case.name, 'target/context completed', flush=True)
        if args.known_check:
            guards = args.out/'guards'; guards.mkdir()
            # Real independent control proofs are corrupted one field at a time.
            for name, mutate in (
                ('verification', lambda p: p.update(all_qualified=False)),
                ('kind', lambda p: p.update(result='running')),
                ('case_hash', lambda p: p['inputs'].update({str(cases[0]/'report.json'): '0'*64})),
                ('capture_hash', lambda p: p['inputs'].update({str(cases[0]/'capture.npz'): '0'*64})),
                ('qualification_flag', lambda p: p['cases'][0].update(all_qualified=False)),
                ('spec_binding', lambda p: p['inputs'].update({str(args.study/'report.json'): '0'*64}))):
                bad = load(args.math_audit); mutate(bad)
                path = guards/(name+'.json'); save(path, bad)
                # The complete case receipt path stays beside the original proof.
                for receipt in proof['cases']:
                    if receipt['complete_audit_file']:
                        file = receipt['complete_audit_file']
                        if not (guards/file).exists(): shutil.copy2(args.math_audit.parent/file, guards/file)
                try: terminal(cases[0], path, repo=repo, known=True)
                except ValueError as error: report['guard_rejections'].append(dict(control=name, reason=str(error)))
                else: raise AssertionError('Corrupted independent verification accepted: '+name)
            assert len(report['guard_rejections']) == 6
        report.update(result='locked_source_known_virtual_measured' if args.known_check else 'locked_source_real_virtual_measured',
            no_fit_restart_or_C_or_hearing_change=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
