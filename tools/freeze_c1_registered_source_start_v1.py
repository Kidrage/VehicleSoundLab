"""Freeze known/execution proofs and an OS-verified live snapshot, never factors."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/c1_registered_source_v1'
    reports, sources, bound = {}, set(), {}
    for stage, result in (('known1', 'independent_c1_registered_terminal_known_verified'),
                          ('launch_known1', 'c1_registered_launch_known_verified'),
                          ('execution1', 'c1_single_execution_registered')):
        r = load(evidence/stage/'report.json')
        assert r['result'] == result and r['verification_passed']
        reports[stage] = r
        for name, expected in r['sources'].items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == expected
            sources.add(name)
        for name, expected in r.get('inputs', {}).items():
            assert sha(name) == expected and Path(name).suffix != '.bin'
            bound[name] = expected
    known, launch, executed = (reports[k] for k in ('known1', 'launch_known1', 'execution1'))
    assert (known['full_terminal_cases'], known['exact_zero_cases'], known['corruptions_rejected']) == (3, 1, 6)
    assert (launch['successes'], launch['rejected']) == (1, 6)
    assert len(known['known_factor_files_sha256']) == 12
    for name, expected in known['known_factor_files_sha256'].items():
        assert sha(name) == expected
    spec = load(executed['canonical_execution'])
    assert executed['execution_spec_sha256'] == sha(executed['canonical_execution']) == sha(executed['storage_execution'])
    assert (len(spec['source_closure']), len(spec['input_closure'])) == (206, 144)
    original_report = load(a.workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
    original = original_report['pair']['spec']
    e, d = Path(original['canonical_claim']), Path(original['storage_claim'])
    for root in (e, d):
        for filename in ('run_spec.json', 'pair_receipt.json', 'execution_spec.json', 'launch_intent.json'):
            bound[str(root/filename)] = sha(root/filename)
    assert (e/'launch_intent.json').read_bytes() == (d/'launch_intent.json').read_bytes()
    intent = load(e/'launch_intent.json')
    pid = intent['pid']
    assert type(pid) is int and pid == 277576
    script = '''
$ErrorActionPreference = 'Stop'
$job = Get-CimInstance Win32_Process -Filter 'ProcessId = 277576'
if ($null -eq $job) { throw 'The originally live source process is absent; inspect terminal evidence, never restart.' }
$process = Get-Process -Id 277576 -ErrorAction Stop
[ordered]@{ pid = $job.ProcessId; command_line = $job.CommandLine;
    creation_date = $job.CreationDate; cpu_seconds = $process.CPU;
    working_set_bytes = $process.WorkingSet64; private_memory_bytes = $process.PrivateMemorySize64
} | ConvertTo-Json -Depth 3
'''
    observed = json.loads(subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout)
    assert observed['pid'] == pid and 'run_c1_registered_source_v1.py' in observed['command_line']
    progress = load(d/'run1/progress.json')
    assert progress['pid'] == pid and progress['status'] == 'running'
    assert not (d/'execution_result.json').exists()
    snapshot = dict(result='OS_verified_live_source_observation', observed_utc=datetime.now(timezone.utc).isoformat(),
        actual_process=observed, saved_progress_snapshot=progress,
        same_exec_session=62945, no_terminal_result_yet=True,
        active_factor_files_NOT_read_or_copied=True, no_speedup_or_actual_peak_or_completion_claim=True)
    save(evidence/'live_observation1.json', snapshot)
    previous = load(repo/'research/c1_fit_registration_v1_summary.json')
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(a.workspace/'baselines/c1_fit_registration_v1/evidence'/filename)
        assert len(values) == count
        for name, expected in values.items():
            assert sha(repo/name) == expected
            sources.add(name)
        save(evidence/filename, values)
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected
    for name, expected in original['toolchain']['native_files_sha256'].items():
        assert sha(name) == expected
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/C1单段完整提取启动V1.md', 'research/c1_registered_source_next_v1_plan.json',
        'research/locked_source_diagnostics_next_v1_plan.json',
        'tools/freeze_c1_registered_source_start_v1.py', 'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    bases = (('workspace', a.workspace), ('repository', repo),
             ('storage', Path('D:/VehicleSoundLab-Work/source_fit_storage_v1')))
    for name, expected in bound.items():
        path = Path(name)
        assert sha(path) == expected
        prefix, base = next((prefix, base) for prefix, base in bases if path.is_relative_to(base))
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='c1_registered_source_start_evidence_frozen',
        known_terminal_complete_cases=3, known_exact_zero_cases=1, known_corruptions=6,
        known_existing_factors_verified=12, known_maximum_comparison_error=max(max(c.get('maximum_errors', {'zero':0}).values()) for c in known['cases']),
        launch_known_successes=1, launch_known_rejections=6,
        actual_source_process_verified_live=snapshot,
        actual_only_label='F3 Fifth First Late', actual_pid=pid, exec_session=62945,
        registration_sha256=intent['registration_sha256'], execution_spec_sha256=executed['execution_spec_sha256'],
        source_closure_count=206, input_closure_count=144, geometry=spec['geometry'],
        canonical_claim=str(e), storage_claim=str(d),
        real_fit_started=True, real_fit_terminal=False,
        real_source_fidelity_NOT_yet_evaluated=True, eligible_for_later_source_statistics=False,
        live_factors_copied_or_hashed=False, previous_known_factors_copied=False,
        original124sources101inputs151conditionalbindings_preserved=True,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_defaults_driver_owned_takes_room_or_hearing_change=True,
        full_goal='ACTIVE: autonomous jointLR/naturalHF/multipleactualengines/allstates/V6fivebuses/independentphysical7.1.4',
        next_plan='research/c1_registered_source_next_v1_plan.json',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/c1_registered_source_start_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/c1_registered_source_start_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['c1_registered_source_start_v1', 'baselines/c1_registered_source_start_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Saved full known3+zero/6corruptions/12factors and unique launch proof; ONE FirstLate actual full D fit started',
        'OS verified LIVE PID277576/session62945; no terminal fidelity/statistics/runtime qualification; never restart',
        'research/C1单段完整提取启动V1.md | research/c1_registered_source_start_v1_summary.json',
        'baselines/c1_registered_source_start_v1/validation.json'])
    print('C1_REGISTERED_START_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
