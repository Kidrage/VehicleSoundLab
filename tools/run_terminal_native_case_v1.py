"""Finite read-only four-stage diagnosis of one already-audited terminal case.

Uses an explicit independent mathematical audit. Does not alter the original
six-case publication, restart either stopped job, or perform any extraction.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'case', 'math-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={},
             only_one_finite_dependent_run=True, terminal_single_case_only=True,
             original_producer_not_restarted=True)
    label = a.case.name
    base = a.out/label
    base.mkdir()
    case_report = dict(result='running', label=label, steps=[])
    try:
        proof = load(a.math_audit)
        assert proof['result']=='independent_waveform_file_real_verified' and proof['verification_passed']
        row = next(c for c in proof['cases'] if c['label']==label)
        assert row['verification_passed'] and row['producer_sha256']==sha(a.case/'report.json')
        spec = load(a.case.parent/'run_spec.json')
        assert label in spec['declared_cases'] and len(spec['declared_cases'])==6
        for path in (a.math_audit, a.case/'report.json', a.case/'capture.npz', a.case.parent/'run_spec.json'):
            r['inputs'][str(path)] = sha(path)
        names = set(spec['sources']) | set(proof['sources']) | {'tools/run_terminal_native_case_v1.py',
            'tools/run_extraction_sound_cases_v2.py', 'tools/audit_extraction_sound_cases_v2.py',
            'tools/run_native_clock_case_v1.py', 'tools/audit_native_clock_case_v1.py'}
        for folder in ('native_clock_case_v1', 'native_clock_case_audit_v1',
                       'native_clock_render_v1', 'extraction_sound_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
            for contract in (spec, proof):
                if name in contract['sources']:
                    assert r['sources'][name]==contract['sources'][name]
        save(a.out/'run_spec.json', dict(pid=os.getpid(), sources=r['sources'], inputs=r['inputs'],
            declared_cases=[label], original_six_cases=spec['declared_cases'], no_extraction=True))
        save(a.out/'report.json', r)
        native = a.workspace/'references/analysis/native_clock_render_v1'
        meter = a.workspace/'references/analysis/extraction_sound_v1'
        common = ['--workspace', str(a.workspace)]
        jobs = (
            ('virtual', 'tools/run_extraction_sound_cases_v2.py', common+[
                '--study', str(a.case), '--math-audit', str(a.math_audit),
                '--meter-study', str(meter/'known2'), '--meter-audit', str(meter/'known_composed_audit1'),
                '--out', str(base/'virtual')]),
            ('virtual_audit', 'tools/audit_extraction_sound_cases_v2.py', common+[
                '--study', str(base/'virtual'), '--out', str(base/'virtual_audit')]),
            ('native', 'tools/run_native_clock_case_v1.py', common+[
                '--case', str(a.case), '--math-audit', str(a.math_audit),
                '--native-study', str(native/'prepare1'), '--native-audit', str(native/'prepare_audit1'),
                '--known-study', str(native/'known1'), '--known-audit', str(native/'known_audit1'),
                '--out', str(base/'native')]),
            ('native_audit', 'tools/audit_native_clock_case_v1.py', common+[
                '--study', str(base/'native'), '--out', str(base/'native_audit')]))
        for tag, script, arguments in jobs:
            for name, digest in r['sources'].items():
                assert sha(repo/name)==sha(a.out/'exact_sources'/name)==digest
            for name, digest in r['inputs'].items():
                assert sha(name)==digest
            command = [sys.executable, str(repo/script), *arguments]
            log = base/(tag+'.log')
            print('TERMINAL_NATIVE_START', label, tag, flush=True)
            with log.open('w', encoding='utf-8', newline='\n') as stream:
                child = subprocess.run(command, cwd=repo, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
            case_report['steps'].append(dict(step=tag, command=command, exit_code=child.returncode,
                log=log.name, log_sha256=sha(log)))
            save(base/'report.json', case_report)
            if child.returncode:
                raise RuntimeError('Terminal-case diagnostic failed: '+tag+'; '+str(log))
        measured, audit = load(base/'native/report.json'), load(base/'native_audit/report.json')
        va = load(base/'virtual_audit/report.json')
        assert va['all_consumer_checks_passed'] and va['actual_recorded_case_qualified']
        assert va['producer_sha256']==sha(base/'virtual/report.json')
        assert audit['verification_passed'] and audit['producer_sha256']==sha(base/'native/report.json')
        flags = {}
        for key in ('source_solver_qualified', 'source_fidelity_qualified',
                    'native16_32_convergence_passed', 'eligible_for_later_source_statistics'):
            assert measured[key]==audit[key]
            flags[key] = measured[key]
        case_report.update(result='real_case_virtual_and_native_diagnostics_verified', **flags,
            virtual_report_sha256=sha(base/'virtual/report.json'),
            virtual_audit_sha256=sha(base/'virtual_audit/report.json'),
            native_report_sha256=sha(base/'native/report.json'),
            native_audit_sha256=sha(base/'native_audit/report.json'), no_source_C_or_hearing_promotion=True)
        save(base/'report.json', case_report)
        r['cases'].append(dict(label=label, report=label+'/report.json',
            report_sha256=sha(base/'report.json'), **flags))
        r.update(result='terminal_single_case_diagnostics_verified', no_source_C_or_hearing_promotion=True)
        save(a.out/'report.json', r)
        print('TERMINAL_NATIVE_COMPLETE', label, flags, flush=True)
    except BaseException as error:
        case_report.update(result='failed', error=repr(error))
        save(base/'report.json', case_report)
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
