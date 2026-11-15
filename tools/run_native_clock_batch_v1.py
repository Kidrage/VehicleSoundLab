"""Finite postprocessing of the SAME six-case producer, never a new extraction."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from research_archive_v1 import load, save, sha
from native_clock_batch_v1.process import OriginalProcess
from native_clock_batch_v1.pipeline import consume


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'producer', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), cases=[], inputs={}, sources={},
             only_one_finite_dependent_run=True, producer_directory=str(a.producer))
    original = None
    started = time.monotonic()
    try:
        spec_file = a.producer / 'run_spec.json'
        spec = load(spec_file)
        prior = a.workspace / 'baselines/native_clock_case_v1'
        prior_summary = repo / 'research/native_clock_case_v1_summary.json'
        assert sha(prior / 'manifest.json') == load(prior_summary)['manifest_sha256']
        anchor = 'inputs/external/references/analysis/waveform_file_real_v1/real1/run_spec.json'
        entry = next(row for row in load(prior / 'manifest.json')['files'] if row['path'] == anchor)
        assert sha(spec_file) == sha(prior / anchor) == entry['sha256'], 'Not the original frozen producer spec'
        for path in (prior / 'manifest.json', prior / anchor, prior_summary):
            r['inputs'][str(path)] = sha(path)
        assert spec['only_one_sequential_run'] and len(spec['declared_cases']) == 6
        assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
        for name, digest in spec['sources'].items():
            assert sha(repo / name) == digest
        for name, digest in spec['inputs'].items():
            assert sha(name) == digest
        r['inputs'][str(spec_file)] = sha(spec_file)
        r['producer_pid'] = spec['pid']
        r['declared_cases'] = spec['declared_cases']
        original = OriginalProcess(spec['pid'])
        initial = original.state()
        publication = load(a.producer / 'report.json')
        assert publication['pid'] == spec['pid'] and publication['declared_cases'] == spec['declared_cases']
        if not initial['live']:
            assert publication['result'] == 'waveform_file_real_six_measured' and len(publication['cases']) == 6
        r['initial_original_process_state'] = initial
        names = {'tools/run_native_clock_batch_v1.py', 'research/native_clock_batch_v1_plan.json',
                 'tools/research_archive_v1.py', 'tools/run_extraction_sound_cases_v2.py',
                 'tools/audit_extraction_sound_cases_v2.py', 'tools/run_native_clock_case_v1.py',
                 'tools/audit_native_clock_case_v1.py'}
        for folder in ('native_clock_batch_v1', 'native_clock_case_v1', 'native_clock_case_audit_v1',
                       'native_clock_render_v1', 'extraction_sound_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo / 'tools' / folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest); r['sources'][name] = sha(dest)

        def verify_sources():
            assert sha(spec_file) == r['inputs'][str(spec_file)], 'Original producer spec changed'
            for name, digest in r['sources'].items():
                assert sha(repo / name) == sha(a.out / 'exact_sources' / name) == digest, name
            for name, digest in spec['sources'].items():
                assert sha(repo / name) == digest, name

        save(a.out / 'run_spec.json', dict(schema='vsl.native_clock_dependent_batch/1',
            pid=os.getpid(), producer_pid=spec['pid'], producer_spec_sha256=sha(spec_file),
            declared_cases=spec['declared_cases'], sources=r['sources'], inputs=r['inputs'],
            initial_original_process_state=initial, finite_six_cases_only=True))
        save(a.out / 'report.json', r)
        print('REAL_NATIVE_BATCH_PID', os.getpid(), 'ORIGINAL_PID', spec['pid'], flush=True)
        for label in spec['declared_cases']:
            last_print = -60.
            stopped_reads = 0
            while True:
                try:
                    publication = load(a.producer / 'report.json')
                except (OSError, json.JSONDecodeError):
                    # Mutable JSON publication may be in progress even after
                    # the process exits; it is never an authoritative stop.
                    state = original.state()
                    if not state['live']:
                        stopped_reads += 1
                        if stopped_reads >= 2:
                            r.update(result='original_producer_stopped_with_unreadable_publication',
                                original_process_state=state, waiting_for=label,
                                elapsed_seconds_PC_only=time.monotonic() - started)
                            save(a.out / 'report.json', r)
                            return
                    time.sleep(15)
                    continue
                assert publication['pid'] == spec['pid'] and publication['declared_cases'] == spec['declared_cases']
                available = {c['label']: c for c in publication['cases']}
                assert set(available) <= set(spec['declared_cases'])
                state = original.state()
                r.update(waiting_for=label, original_process_state=state,
                         published_audited_cases=len(available), elapsed_seconds_PC_only=time.monotonic() - started)
                if label in available:
                    published = available[label]
                    assert published['verification_passed']
                    assert published['case_report_sha256'] == sha(a.producer / published['case_report'])
                    assert published['audit_report_sha256'] == sha(a.producer / published['audit_report'])
                    verify_sources()
                    result = consume(label, repo=repo, workspace=a.workspace, producer=a.producer,
                                     out=a.out, verify_sources=verify_sources)
                    r['cases'].append(dict(label=label, report=label + '/report.json',
                        report_sha256=sha(a.out / label / 'report.json'),
                        **{key: result[key] for key in ('source_solver_qualified', 'source_fidelity_qualified',
                           'native16_32_convergence_passed', 'eligible_for_later_source_statistics')}))
                    save(a.out / 'report.json', r)
                    print('REAL_NATIVE_BATCH_CASE_VERIFIED', label, 'eligible',
                          result['eligible_for_later_source_statistics'], flush=True)
                    break
                if not state['live']:
                    stopped_reads += 1
                    if stopped_reads >= 2:
                        r.update(result='original_producer_stopped_before_all_cases_published',
                                 elapsed_seconds_PC_only=time.monotonic() - started)
                        save(a.out / 'report.json', r)
                        print('REAL_NATIVE_BATCH_STOPPED_ORIGINAL', state, flush=True)
                        return
                if time.monotonic() - last_print >= 60:
                    save(a.out / 'report.json', r)
                    print('REAL_NATIVE_BATCH_WAIT', label, 'published', len(available),
                          'original_live', state['live'], flush=True)
                    last_print = time.monotonic()
                time.sleep(15)
        assert len(r['cases']) == 6
        r.update(result='six_real_case_virtual_native_diagnostics_verified',
                 all_independent_consumer_audits_passed=True,
                 all_eligible_for_later_source_statistics=all(c['eligible_for_later_source_statistics'] for c in r['cases']),
                 elapsed_seconds_PC_only=time.monotonic() - started,
                 no_source_C_or_default_or_hearing_promotion=True)
        save(a.out / 'report.json', r)
        print('REAL_NATIVE_BATCH_COMPLETE', r['all_eligible_for_later_source_statistics'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error), elapsed_seconds_PC_only=time.monotonic() - started)
        save(a.out / 'report.json', r)
        raise
    finally:
        if original is not None:
            original.close()


if __name__ == '__main__':
    main()
