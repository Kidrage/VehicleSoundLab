"""Freeze source transfer controls, six inputs, regressions and exact sources."""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/source_resampling_v1'
    original = a.workspace/'references/analysis/waveform_file_real_v1/real1'
    spec = load(original/'run_spec.json')
    assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
    for name, digest in spec['sources'].items(): assert sha(repo/name) == digest
    for name, digest in spec['inputs'].items(): assert sha(name) == digest
    sources, bound = set(spec['sources']), dict(spec['inputs'])
    for folder, audit_folder, count in (('known1', 'known_audit1', 8), ('real1', 'real_audit1', 6), ('review1', 'review_audit1', 6)):
        producer, audit = load(evidence/folder/'report.json'), load(evidence/audit_folder/'report.json')
        assert audit['verification_passed'] and audit['producer_sha256'] == sha(evidence/folder/'report.json')
        assert len(producer['cases']) == count
        if folder == 'review1': assert audit['numeric_checks'] == 88 and audit['all_18_radius_pairs_verified']
        for name, digest in producer['sources'].items():
            assert sha(repo/name) == digest
            sources.add(name)
        for name, digest in producer['inputs'].items():
            assert sha(name) == digest; bound[name] = digest
    review = load(evidence/'review1/report.json')
    assert not review['original_source_fidelity_qualified'] and not review['eligible_for_later_source_statistics']
    assert review['saved_fit_cross_reference_complex_NRMSE']['sinc128'][-1] > review['saved_fit_cross_reference_complex_NRMSE']['legacy'][-1]
    for path in (original/'run_spec.json', original/'report.json', a.workspace/'baselines/native_error_budget_v1/manifest.json'):
        bound[str(path)] = sha(path)
    prior = a.workspace/'baselines/native_error_budget_v1/evidence'
    inputs = {}
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/filename); assert len(values) == count
        for name, digest in values.items(): assert sha(repo/name) == digest
        save(evidence/filename, values); inputs['protected/'+filename] = prior/filename
    assert subprocess.check_output(['git', 'show', '3a65b4c:handoff/C文件索引.csv'], cwd=repo) == (repo/'handoff/C文件索引.csv').read_bytes()
    for name, digest in bound.items():
        path = Path(name); assert sha(path) == digest and path.suffix != '.bin'
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/源重采样传递V1.md', 'research/source_resampling_next_v1_plan.json',
        'tools/freeze_source_resampling_v1.py', 'tools/audit_source_resampling_archive_v1.py'})
    validation = dict(result='source_resampling_transfer_evidence_frozen',
        previous_goal_turn='native_error_budget actual signed decomposition/publication: progress',
        this_goal_turn='known-qualified direct bandlimited source query, six independently verified real transfers and preserved fixed-fit regression: progress',
        known_cases_verified=8, real_cases_verified=6, publication_checks=88, all_radius_pairs_verified=18,
        original96sources_unchanged=True, original71inputs_unchanged=True,
        original_jobs_not_restarted=True, first_case_never_refit=True, original_remaining_five_never_fitted=True,
        C_files_unchanged=670, voice_files_unchanged=82, F2_files_unchanged=3,
        protected_C_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        resampling_improvement_is_not_perceptual_or_sustained_voice_qualification=True,
        saved_old_fit_cross_reference_regression_retained=True,
        all_four_methods_and_weak_absolute_powers_retained=True, no_factors_copied=True,
        cases=review['cases'], saved_fit_cross_reference_complex_NRMSE=review['saved_fit_cross_reference_complex_NRMSE'],
        full_goal='ACTIVE: sustained jointLR/V6fivebuses/multiengine/allstates/independent physical7.1.4',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/source_resampling_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/source_resampling_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['source_resampling_v1', 'baselines/source_resampling_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known8 then real6 source transfer independently verified;88 publication checks/all18radiuspairs',
        '670C-H82voice3F2/index exact;old-fit changed-reference regression retained;no source/C/hearing promotion',
        'research/源重采样传递V1.md | research/source_resampling_v1_summary.json', 'baselines/source_resampling_v1/validation.json'])
    print('SOURCE_QUERY_FREEZE', receipt, flush=True)


if __name__ == '__main__': main()
