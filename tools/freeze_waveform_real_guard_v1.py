"""Freeze first-terminal diagnostic evidence, retaining every failed attempt.

Complete factor files stay at their original paths; the mathematical audit
has streamed their hashes. This archive records those identities, not copies.
"""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/waveform_real_guard_v1'
    original = a.workspace/'references/analysis/waveform_file_real_v1/real1'
    case = original/'F3 Fifth First Early'
    prior = a.workspace/'baselines/native_clock_case_v1'
    spec = load(original/'run_spec.json')
    assert len(spec['sources'])==96 and len(spec['inputs'])==71
    assert load(original/'report.json')['result']=='failed'
    assert load(original/'report.json')['current_case_index']==0
    for name, digest in spec['sources'].items():
        assert sha(repo/name)==sha(original/'exact_sources'/name)==digest
    for name, digest in spec['inputs'].items():
        assert sha(name)==digest
    math = load(evidence/'real_audit1/report.json')
    native = load(evidence/'native1/F3 Fifth First Early/native/report.json')
    na = load(evidence/'native1/F3 Fifth First Early/native_audit/report.json')
    publication = load(evidence/'review_audit3/report.json')
    assert math['verification_passed'] and not math['all_qualified']
    assert native['source_solver_qualified'] and not native['source_fidelity_qualified']
    assert native['native16_32_convergence_passed'] and not native['eligible_for_later_source_statistics']
    assert na['verification_passed'] and publication['all_publication_fields_verified']
    assert na['producer_sha256']==sha(evidence/'native1/F3 Fifth First Early/native/report.json')
    inputs = {}
    for label, filename, count in (('C', 'C_files_sha256.json', 670),
                                    ('voice', 'voice_files_sha256.json', 82),
                                    ('F2', 'F2_files_sha256.json', 3)):
        path = prior/'evidence'/filename
        values = load(path)
        assert len(values)==count
        for name, digest in values.items():
            assert sha(repo/name)==digest, name
        save(evidence/filename, values)
        inputs['protected/'+filename] = path
    old_index = subprocess.check_output(['git', 'show', '3a65b4c:handoff/C文件索引.csv'], cwd=repo)
    assert old_index==(repo/'handoff/C文件索引.csv').read_bytes()
    for name in ('run_spec.json', 'report.json'):
        inputs['original_producer/'+name] = original/name
    for name in ('report.json', 'capture.npz', 'preflight.json', 'progress.json'):
        inputs['original_first_case/'+name] = case/name
    for path in (original/'F3 Fifth First Early_audit').rglob('*'):
        if path.is_file():
            inputs['original_failed_audit/'+path.relative_to(original/'F3 Fifth First Early_audit').as_posix()] = path
    for name, path in spec['inputs'].items():
        path = Path(name)
        if path.is_relative_to(a.workspace):
            relative = 'external/'+path.relative_to(a.workspace).as_posix()
        elif path.is_relative_to(repo):
            relative = 'repository/'+path.relative_to(repo).as_posix()
        else:
            raise ValueError('Unexpected original input root: '+str(path))
        inputs[relative] = path
    batch = a.workspace/'references/analysis/native_clock_batch_v1'
    stopped = load(batch/'run1/report.json')
    assert stopped['result']=='original_producer_stopped_before_all_cases_published'
    assert not stopped['original_process_state']['live'] and stopped['original_process_state']['exit_code']==1
    for folder in ('run1', 'process_controls1'):
        for path in (batch/folder).rglob('*'):
            if path.is_file():
                inputs['original_dependent/'+folder+'/'+path.relative_to(batch/folder).as_posix()] = path
    sources = set(spec['sources']) | set(math['sources']) | {
        'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/真实首段复核与原生诊断V1.md', 'research/真实提取有限后处理V1.md',
        'research/waveform_real_guard_v1_plan.json', 'research/waveform_real_guard_next_v1_plan.json',
        'research/native_clock_batch_v1_plan.json', 'research/native_clock_batch_next_v1_plan.json',
        'research/actual_native_review_v1_plan.json',
        'tools/diagnose_waveform_real_guard_v1.py', 'tools/run_terminal_native_case_v1.py',
        'tools/review_actual_native_cases_v1.py', 'tools/audit_actual_native_review_v1.py',
        'tools/run_native_clock_batch_v1.py', 'tools/check_native_clock_batch_process_v1.py',
        'tools/freeze_waveform_real_guard_v1.py'}
    for folder in ('waveform_real_guard_v1', 'native_clock_batch_v1'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/folder).glob('*.py'))
    review = load(evidence/'review3/F3 Fifth First Early.json')
    comparison = native['comparisons']['fitted16_vs_raw']
    raw = review['signals']['raw']['mean_power_FS2']
    weak_fraction = sum(raw[-1])/sum(sum(band) for band in raw)
    main = comparison['signed_changes']['broad']
    validation = dict(result='first_actual_terminal_numerics_and_native_diagnostics_frozen',
        previous_goal_turn='MCPS-only answer: no synthesis progress',
        this_goal_turn='Actual first-case audit repair, verified native diagnostics and observedHF/LR/time evidence: progress',
        original_jobs_terminal=True, original_jobs_not_restarted=True,
        original_sources_bound_and_unchanged=96, original_inputs_bound_and_unchanged=71,
        C_files_unchanged=670, voice_files_unchanged=82, F2_files_unchanged=3, C_index_unchanged=True,
        independent_mathematical_verification=True, source_solver_qualified=True,
        source_fidelity_qualified=False, native16_32_convergence_passed=True,
        eligible_for_later_source_statistics=False, all_original_gates_unchanged=True,
        original_failed_audit=load(original/'F3 Fifth First Early_audit/report.json'),
        actual_virtual_metrics=math['cases'][0]['metrics'],
        actual_native_raw_errors={k:v for k,v in comparison.items() if k!='signed_changes'},
        native16_32_errors={k:v for k,v in native['comparisons']['fitted16_vs_fitted32'].items() if k!='signed_changes'},
        native0_14k_max_abs_band_power_dB=max(abs(v) for band in main['power_change_dB'][:5] for v in band),
        native0_14k_max_abs_LR_complex_component_change=max(abs(v) for band in main['complex_coherence_change'][:5] for v in band),
        native0_14k_max_abs_CV_change=max(abs(v) for band in main['CV_change'][:5] for v in band),
        native14k_plus_fraction_of_all_measured_Welch_power=weak_fraction,
        no_factors_copied=True, no_new_voice_or_C_or_hearing_promotion=True,
        uncompleted_original_labels=spec['declared_cases'][1:],
        full_goal='ACTIVE: V6fivebuses, multiengine/all driving states, sustained jointLR, independent physical7.1.4',
        input_archive_locations={str(path):name for name,path in inputs.items()},
        protected_C_index_sha256=sha(repo/'handoff/C文件索引.csv'))
    root = a.workspace/'baselines/waveform_real_guard_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    summary = dict(validation, archive=str(root), **receipt)
    save(repo/'research/waveform_real_guard_v1_summary.json', summary)
    print('FIRST_ACTUAL_FREEZE', receipt, flush=True)


if __name__ == '__main__':
    main()
