"""Freeze terminal new-source diagnostics; exclude the live real extraction."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args(); repo = Path(__file__).resolve().parents[1]
    evidence = args.workspace/'references/analysis/locked_source_diagnostics_v1'
    bound, sources = {}, set()
    reports = {}
    for name, expected in (('virtual_known1', 'locked_source_known_virtual_measured'),
            ('virtual_known_audit1', 'independent_locked_source_virtual_verified'),
            ('virtual_stereo_audit1', 'independent_locked_source_virtual_stereo_verified'),
            ('native_references1', 'locked_source_native_references_checked')):
        report = load(evidence/name/'report.json'); assert report['result'] == expected
        reports[name] = report
        for relative, wanted in report.get('sources', {}).items():
            assert sha(repo/relative) == wanted; sources.add(relative)
        for path, wanted in report.get('inputs', {}).items():
            assert sha(path) == wanted; bound[path] = wanted
    for row in reports['virtual_known1']['cases']:
        path = evidence/'virtual_known1'/row['report']; assert sha(path) == row['sha256']
        for original, wanted in load(path)['inputs'].items():
            assert sha(original) == wanted; bound[original] = wanted
    assert len(reports['virtual_known1']['cases']) == 3 and len(reports['virtual_known1']['guard_rejections']) == 6
    assert reports['virtual_known_audit1']['all_consumer_checks_passed']
    assert reports['virtual_known_audit1']['producer_sha256'] == sha(evidence/'virtual_known1/report.json')
    assert reports['virtual_stereo_audit1']['all_stereo_checks_passed']
    assert reports['virtual_stereo_audit1']['producer_sha256'] == sha(evidence/'virtual_known1/report.json')
    assert reports['virtual_stereo_audit1']['prior_audit_sha256'] == sha(evidence/'virtual_known_audit1/report.json')
    assert len(reports['native_references1']['cases']) == 5 and reports['native_references1']['all_reference_checks_passed']
    prior = args.workspace/'baselines/locked_source_adapter_v1/evidence'
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/filename); assert len(values) == count
        for name, wanted in values.items(): assert sha(repo/name) == wanted; sources.add(name)
        save(evidence/filename, values)
    prior_summary = load(repo/'research/locked_source_adapter_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == prior_summary['protected_C_index_sha256']
    assert all(sha(repo/name) == wanted for name, wanted in prior_summary['protected_hearings_sha256'].items())
    live = args.workspace/'references/analysis/locked_source_fit_v1/real1'
    spec = load(live/'run_spec.json')
    assert len(spec['sources']) == 124 and len(spec['inputs']) == 101 and spec['pid'] == 65232
    for name, wanted in spec['sources'].items(): assert sha(repo/name) == wanted
    for path, wanted in spec['inputs'].items(): assert sha(path) == wanted
    command = "Get-CimInstance Win32_Process -Filter 'ProcessId = 65232' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    import json
    observation = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True))
    assert observation['ProcessId'] == 65232 and 'run_locked_source_real_v1.py' in observation['CommandLine']
    save(evidence/'real_process_observation.json', observation)
    shutil.copy2(live/'run_spec.json', evidence/'real_launch_spec.json')
    inputs = {}
    for path, wanted in bound.items():
        path = Path(path); assert sha(path) == wanted and path.suffix != '.bin'
        prefix, base = ('workspace', args.workspace) if path.is_relative_to(args.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools/locked_source_diagnostics_v1').glob('*.py'))
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/新声源的高频与左右诊断V1.md', 'research/locked_source_diagnostics_next_v1_plan.json',
        'tools/run_locked_source_native_v1.py', 'tools/audit_locked_source_native_v1.py',
        'tools/check_locked_source_native_references_v1.py', 'tools/freeze_locked_source_diagnostics_v1.py',
        'tools/audit_locked_source_diagnostics_bindings_v1.py', 'tools/verify_research_archive_independent_v1.py'})
    validation = dict(result='locked_source_diagnostics_evidence_frozen', previous_goal_turn='progress: qualified adapter and real preparation',
        this_goal_turn='progress: executed new virtual consumer/stereo checks and five native-reference bridges',
        virtual_known_cases=3, corrupt_binding_rejections=6, direct_stereo_observations=12, real_native_reference_cases=5,
        signed_linear_values=sum(row['signed_linear_changes_checked'] for row in reports['virtual_known_audit1']['cases']),
        maximum_stereo_error=max(reports['virtual_stereo_audit1']['maximum_errors'].values()),
        actual_new_fit_admission_exercised=False, actual_new_fitted_native_render_qualified=False,
        retained_legacy_cross_FFT_normalized_failures=5, physical_source_separation_qualified=False,
        protected_hearings_sha256=prior_summary['protected_hearings_sha256'],
        protected_C_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        real_job_observation=observation, real_session=62289, protected_live_sources=124, protected_live_inputs=101,
        original_first_case_never_refit=True, original_jobs_not_restarted=True,
        no_live_real_files_or_original_factors_copied=True, no_C_or_hearing_or_sustained_promotion=True,
        full_goal='ACTIVE: autonomousjointLR/V6fivebuses/multiengine/fullstates/separatephysical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = args.workspace/'baselines/locked_source_diagnostics_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/locked_source_diagnostics_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['locked_source_diagnostics_v1', 'baselines/locked_source_diagnostics_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'], 'Newmethod virtual3/guard6/stereo12 and actual5 native-reference bridges PASS',
        '670C-H82voice3F2/index/hearings exact;new fitted native admission pending;no C/hearing promotion',
        'research/新声源的高频与左右诊断V1.md | research/locked_source_diagnostics_v1_summary.json', 'baselines/locked_source_diagnostics_v1/validation.json'])
    print('LOCKED_DIAGNOSTICS_FROZEN', receipt, flush=True)


if __name__ == '__main__': main()
