"""Freeze terminal adapter controls/preparation, excluding the live real solve."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args(); repo = Path(__file__).resolve().parents[1]
    study = args.workspace/'references/analysis/locked_source_fit_v1'
    evidence = args.workspace/'references/analysis/locked_source_adapter_v1'
    evidence.mkdir(parents=True, exist_ok=False)
    sources, inputs = set(), {}
    bound = {}
    for name, expected, count in (('known1', 'locked_source_fit_known_measured', 4),
            ('known_audit1', 'independent_locked_source_known_verified', 4),
            ('prepare1', 'locked_source_five_prepared', 5),
            ('prepare_audit1', 'independent_locked_source_preparation_verified', 5)):
        report = load(study/name/'report.json')
        assert report['result'] == expected and len(report['cases']) == count
        if name != 'prepare1': assert report['all_qualified']
        for relative, wanted in report.get('sources', {}).items():
            assert sha(repo/relative) == wanted; sources.add(relative)
        for path, wanted in report['inputs'].items():
            assert sha(path) == wanted; bound[path] = wanted
        shutil.copytree(study/name, evidence/name)
    assert load(study/'known_audit1/report.json')['producer_sha256'] == sha(study/'known1/report.json')
    assert load(study/'prepare_audit1/report.json')['producer_sha256'] == sha(study/'prepare1/report.json')
    spec_path = args.workspace/'references/analysis/waveform_file_real_v1/real1/run_spec.json'
    original = load(spec_path)
    assert len(original['sources']) == 96 and len(original['inputs']) == 71
    for name, wanted in original['sources'].items(): assert sha(repo/name) == wanted
    for path, wanted in original['inputs'].items(): assert sha(path) == wanted
    prior = args.workspace/'baselines/source_resampling_v1/evidence'
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/filename); assert len(values) == count
        for name, wanted in values.items(): assert sha(repo/name) == wanted
        save(evidence/filename, values); inputs['protected/'+filename] = prior/filename
    assert subprocess.check_output(['git', 'show', '3a65b4c:handoff/C文件索引.csv'], cwd=repo) == (repo/'handoff/C文件索引.csv').read_bytes()
    full = load(repo/'research/waveform_file_full_v1_summary.json')
    hearings = full['protected_hearings_sha256']
    assert all(sha(repo/name) == wanted for name, wanted in hearings.items())
    for path, wanted in bound.items():
        path = Path(path); assert sha(path) == wanted and path.suffix != '.bin'
        if path.is_relative_to(args.workspace): prefix, base = 'workspace', args.workspace
        else: prefix, base = 'repository', repo
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    # Only immutable launch metadata is captured, never the changing real tree.
    real_spec = load(study/'real1/run_spec.json')
    assert real_spec['declared_cases'] == ['F3 Fifth First Mid'] and real_spec['only_one_finite_case']
    sources.update(real_spec['sources'])
    shutil.copy2(study/'real1/run_spec.json', evidence/'real_launch_spec.json')
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/锁定标尺的新声源适配V1.md', 'research/locked_source_adapter_next_v1_plan.json', 'tools/freeze_locked_source_adapter_v1.py',
        'tools/audit_locked_source_adapter_archive_v1.py'})
    known = load(study/'known_audit1/report.json')
    prepared = load(study/'prepare_audit1/report.json')
    validation = dict(result='locked_source_adapter_evidence_frozen',
        previous_goal_turn='MCPS-only: no synthesis progress',
        this_goal_turn='changed-source locked-calibration adapter, dense-QR controls, real-five preparation independently verified: progress',
        known_cases=4, independent_QR_cases=3, invalid_rejections=6, prepared_real_cases=5,
        known_QR_relative_coefficient_differences=[row['independent_QR_relative_coefficient_difference'] for row in known['cases']],
        prepared=prepared['cases'], original96sources71inputs_unchanged=True,
        C_files_unchanged=670, voice_files_unchanged=82, F2_files_unchanged=3,
        protected_C_index_sha256=sha(repo/'handoff/C文件索引.csv'), protected_hearings_sha256=hearings,
        original_jobs_never_restarted=True, original_first_case_never_refit=True,
        real_first_mid_started=True, real_result_not_qualified_by_this_archive=True,
        real_launch_spec_sha256=sha(study/'real1/run_spec.json'), real_pid=real_spec['pid'], real_session=62289,
        no_live_real_files_or_original_factors_copied=True,
        no_source_or_C_or_hearing_promotion=True,
        full_goal='ACTIVE: sustained jointLR/V6fivebuses/multiengine/allstates/independentphysical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = args.workspace/'baselines/locked_source_adapter_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/locked_source_adapter_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['locked_source_adapter_v1', 'baselines/locked_source_adapter_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'], 'Known4/denseQR3/invalid6 and full288 real5 preparation independently verified',
        '670C-H82voice3F2/index/hearings exact;first original never refit;new firstMid is separate live job',
        'research/锁定标尺的新声源适配V1.md | research/locked_source_adapter_v1_summary.json', 'baselines/locked_source_adapter_v1/validation.json'])
    print('LOCKED_ADAPTER_FROZEN', receipt, flush=True)


if __name__ == '__main__': main()
