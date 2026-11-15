"""Freeze complete signed-error evidence, failed audits and original bindings."""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/native_error_budget_v1'
    producer = load(evidence/'real1/report.json')
    audit = load(evidence/'audit1/report.json')
    review = load(evidence/'review1/report.json')
    publication = load(evidence/'review_audit3/report.json')
    assert producer['result'] == 'actual_native_error_budget_measured'
    assert audit['verification_passed'] and audit['producer_sha256'] == sha(evidence/'real1/report.json')
    assert publication['all_publication_fields_verified']
    assert publication['producer_sha256'] == sha(evidence/'review1/report.json')
    assert len(publication['checks']) == 111
    for label in ('review_audit1', 'review_audit2'):
        assert load(evidence/label/'report.json')['result'] == 'failed'
    original = a.workspace/'references/analysis/waveform_file_real_v1/real1'
    spec = load(original/'run_spec.json')
    assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
    assert load(original/'report.json')['result'] == 'failed'
    for name, digest in spec['sources'].items():
        assert sha(repo/name) == sha(original/'exact_sources'/name) == digest
    for name, digest in spec['inputs'].items():
        assert sha(name) == digest
    bound = dict(producer['inputs'], **review['inputs'])
    bound[str(original/'run_spec.json')] = sha(original/'run_spec.json')
    bound[str(original/'report.json')] = sha(original/'report.json')
    bound[str(a.workspace/'baselines/waveform_real_guard_v1/manifest.json')] = sha(
        a.workspace/'baselines/waveform_real_guard_v1/manifest.json')
    inputs = {}
    for name, digest in bound.items():
        assert sha(name) == digest
        path = Path(name)
        assert path.suffix != '.bin'
        if path.is_relative_to(a.workspace):
            relative = 'workspace/'+path.relative_to(a.workspace).as_posix()
        elif path.is_relative_to(repo):
            relative = 'repository/'+path.relative_to(repo).as_posix()
        else:
            raise ValueError('Unexpected bound input root: '+name)
        inputs[relative] = path
    prior = a.workspace/'baselines/waveform_real_guard_v1/evidence'
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/filename)
        assert len(values) == count
        for name, digest in values.items():
            assert sha(repo/name) == digest
        save(evidence/filename, values)
        inputs['protected/'+filename] = prior/filename
    assert subprocess.check_output(['git', 'show', '3a65b4c:handoff/C文件索引.csv'], cwd=repo) == (repo/'handoff/C文件索引.csv').read_bytes()
    sources = set(spec['sources']) | set(producer['sources']) | set(review['sources']) | {
        'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/native_error_budget_v1_plan.json', 'research/native_error_budget_next_v1_plan.json',
        'research/原生误差分解与最高频带V1.md', 'tools/audit_native_error_budget_v1.py',
        'tools/freeze_native_error_budget_v1.py', 'tools/audit_native_error_budget_archive_v1.py'}
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools/native_error_budget_v1').glob('*.py'))
    main_sensitivity = max(v for row in review['sensitivity'] for band in
        row['combined_component_band_NRMSE_relative_raw'][:5] for v in band)
    validation = dict(result='native_signed_error_and_highest_band_evidence_frozen',
        previous_goal_turn='MCPS-only: no synthesis progress',
        this_goal_turn='Actual signed decomposition,111 independently verified publication fields and changed next source-resampler action: progress',
        original96sources_unchanged=True, original71inputs_unchanged=True,
        original_jobs_terminal_not_restarted=True, first_case_not_refit=True,
        remaining_five_original_cases_not_started=True, no_factor_files_copied=True,
        C_files_unchanged=670, voice_files_unchanged=82, F2_files_unchanged=3,
        protected_C_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        all_four_variants_all_query_output_and_Gram_audited=True,
        all_six_pairwise_sensitivities_verified=True,
        publication_fields_verified=len(publication['checks']),
        two_failed_publication_audits_retained=True, original_gates_unchanged=True,
        source_solver_qualified=producer['source_solver_qualified'],
        source_fidelity_qualified=producer['source_fidelity_qualified'],
        native16_32_convergence_passed=producer['native16_32_convergence_passed'],
        eligible_for_later_source_statistics=producer['eligible_for_later_source_statistics'],
        virtual=review['virtual'], physical=review['physical'], sensitivity=review['sensitivity'],
        main0_14k_max_component_sensitivity_NRMSE=main_sensitivity,
        physical_reconstruction_is_not_unique_inverse=True,
        source_resampling_tail_hypothesis_not_yet_qualified=True,
        no_C_voice_timbre_or_hearing_promotion=True,
        full_goal='ACTIVE: sustained jointLR/multiengine/allstates/V6fivebuses/independent physical7.1.4',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    assert validation['source_solver_qualified'] and not validation['source_fidelity_qualified']
    assert not validation['eligible_for_later_source_statistics']
    root = a.workspace/'baselines/native_error_budget_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/native_error_budget_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', [
        'native_error_budget_v1', 'baselines/native_error_budget_v1/manifest.json', str(receipt['file_count']),
        receipt['manifest_sha256'], 'Four signed error components/all queries/all outputs/all Grams and111 publication fields verified',
        '670C-H82voice3F2/index unchanged;original fidelityFALSE;two failed publication audits retained',
        'research/原生误差分解与最高频带V1.md | research/native_error_budget_v1_summary.json',
        'baselines/native_error_budget_v1/validation.json'])
    print('NATIVE_ERROR_FREEZE', receipt, flush=True)


if __name__ == '__main__':
    main()
