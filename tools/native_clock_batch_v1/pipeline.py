"""Sequential checked child processes; source errors never restart extraction."""
from pathlib import Path
import subprocess
import sys
from research_archive_v1 import load, save, sha


def consume(label, *, repo, workspace, producer, out, verify_sources):
    case = Path(producer) / label
    math_audit = Path(producer) / (label + '_audit') / 'report.json'
    base = Path(out) / label
    base.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', label=label, steps=[])
    native = Path(workspace) / 'references/analysis/native_clock_render_v1'
    meter = Path(workspace) / 'references/analysis/extraction_sound_v1'
    common = ['--workspace', str(workspace)]
    jobs = (
        ('virtual', 'tools/run_extraction_sound_cases_v2.py',
         common + ['--study', str(case), '--math-audit', str(math_audit),
                   '--meter-study', str(meter / 'known2'), '--meter-audit', str(meter / 'known_composed_audit1'),
                   '--out', str(base / 'virtual')]),
        ('virtual_audit', 'tools/audit_extraction_sound_cases_v2.py',
         common + ['--study', str(base / 'virtual'), '--out', str(base / 'virtual_audit')]),
        ('native', 'tools/run_native_clock_case_v1.py',
         common + ['--case', str(case), '--math-audit', str(math_audit),
                   '--native-study', str(native / 'prepare1'), '--native-audit', str(native / 'prepare_audit1'),
                   '--known-study', str(native / 'known1'), '--known-audit', str(native / 'known_audit1'),
                   '--out', str(base / 'native')]),
        ('native_audit', 'tools/audit_native_clock_case_v1.py',
         common + ['--study', str(base / 'native'), '--out', str(base / 'native_audit')]),
    )
    try:
        for name, script, arguments in jobs:
            verify_sources()
            log = base / (name + '.log')
            command = [sys.executable, str(Path(repo) / script), *arguments]
            print('REAL_NATIVE_BATCH_START', label, name, flush=True)
            with log.open('w', encoding='utf-8', newline='\n') as stream:
                process = subprocess.run(command, cwd=repo, stdout=stream, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
            row = dict(step=name, command=command, exit_code=process.returncode,
                       log=log.name, log_sha256=sha(log))
            r['steps'].append(row)
            save(base / 'report.json', r)
            if process.returncode:
                raise RuntimeError('Dependent stage failed: ' + name + '; see ' + str(log))
            print('REAL_NATIVE_BATCH_STEP_COMPLETE', label, name, flush=True)
        virtual = load(base / 'virtual/report.json')
        va = load(base / 'virtual_audit/report.json')
        measured = load(base / 'native/report.json')
        na = load(base / 'native_audit/report.json')
        assert va['all_consumer_checks_passed'] and va['producer_sha256'] == sha(base / 'virtual/report.json')
        assert na['verification_passed'] and na['producer_sha256'] == sha(base / 'native/report.json')
        assert va['actual_recorded_case_qualified'] and virtual['result'] == 'extraction_sound_real_case_measured'
        assert measured['result'] == 'actual_native_clock_case_measured'
        for field in ('source_solver_qualified', 'source_fidelity_qualified',
                      'native16_32_convergence_passed', 'eligible_for_later_source_statistics'):
            assert measured[field] == na[field]
            r[field] = measured[field]
        verify_sources()
        r.update(result='real_case_virtual_and_native_diagnostics_verified',
                 virtual_report_sha256=sha(base / 'virtual/report.json'),
                 virtual_audit_sha256=sha(base / 'virtual_audit/report.json'),
                 native_report_sha256=sha(base / 'native/report.json'),
                 native_audit_sha256=sha(base / 'native_audit/report.json'),
                 no_source_C_or_hearing_promotion=True)
        save(base / 'report.json', r)
        return r
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(base / 'report.json', r)
        raise
