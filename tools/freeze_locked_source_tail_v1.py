"""Freeze terminal weak-tail evidence and all unchanged runtime contracts."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/locked_source_tail_v1'
    reports, sources, bound = {}, set(), {}
    for stage, result in (
        ('known1', 'locked_source_tail_known_measured'),
        ('known_audit1', 'independent_locked_source_tail_known_verified'),
        ('real1', 'locked_source_tail_real_measured'),
        ('audit1', 'independent_locked_source_tail_real_verified'),
        ('review1', 'locked_source_tail_review_published'),
        ('review_audit1', 'independent_locked_source_tail_review_verified')):
        row = load(evidence/stage/'report.json')
        assert row['result'] == result
        reports[stage] = row
        for name, expected in row.get('sources', {}).items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == expected
            sources.add(name)
        for name, expected in row.get('inputs', {}).items():
            assert sha(name) == expected and Path(name).suffix != '.bin'
            bound[name] = expected
    for stage, audit in (('known1', 'known_audit1'), ('real1', 'audit1'), ('review1', 'review_audit1')):
        assert reports[audit]['verification_passed']
        assert reports[audit]['producer_sha256'] == sha(evidence/stage/'report.json')
    produced, review = reports['real1'], reports['review1']
    assert not produced['source_fidelity_qualified'] and not produced['eligible_for_later_source_statistics']
    assert reports['known1']['qualification']['all_qualified']
    for stage in ('known1', 'real1'):
        assert reports[stage]['capture_sha256'] == sha(evidence/stage/'capture.npz')
    for name, expected in review['figures'].items():
        assert sha(evidence/'review1'/name) == expected
    prior = a.workspace/'baselines/locked_source_error_v1/evidence'
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/name)
        assert len(values) == count
        for relative, expected in values.items():
            assert sha(repo/relative) == expected
            sources.add(relative)
        save(evidence/name, values)
    previous = load(repo/'research/locked_source_error_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected
    spec_path = Path(produced['source']['binding_file'])
    spec = load(spec_path)
    for name, expected in spec['sources'].items():
        assert sha(repo/name) == sha(spec_path.parent/'exact_sources'/name) == expected
    for name, expected in spec['inputs'].items():
        assert sha(name) == expected
        bound[name] = expected
    conditional_file = a.workspace/'references/analysis/locked_source_diagnostics_followthrough_v1/manifest.json'
    conditional = load(conditional_file)
    assert conditional['run_spec_sha256'] == sha(spec_path)
    assert len(conditional['source_sha256']) == 151
    for name, expected in conditional['source_sha256'].items():
        assert sha(name) == expected
        if Path(name).is_relative_to(repo):
            sources.add(Path(name).relative_to(repo).as_posix())
        else:
            assert Path(name).is_relative_to(a.workspace)
            bound[name] = expected
    bound[str(conditional_file)] = sha(conditional_file)
    case = spec_path.parent/produced['label']
    assert load(spec_path.parent/'report.json')['result'] == 'failed'
    assert load(spec_path.parent/(case.name+'_audit')/'report.json')['result'] == 'failed'
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/源查询弱尾部与共同时间映射V1.md', 'research/locked_source_diagnostics_next_v1_plan.json',
        'research/locked_source_tail_next_v1_plan.json', 'tools/freeze_locked_source_tail_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, expected in bound.items():
        path = Path(name)
        assert sha(path) == expected
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='locked_source_tail_diagnostics_frozen',
        previous_goal_turn='no synthesis progress: MCPS-only estimate',
        this_goal_turn='progress: actual known-first/real highprecision source-query diagnosis, independent all-query/spectra/Gram audits and complete publication',
        actual_case=produced['label'], full_orders=288, nodes=74, frames=produced['frames'],
        known_before_real=True, diagnostic_radii=[512, 1024, 2048],
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        original_virtual_highest_NRMSE=review['original_virtual_highest_NRMSE'],
        real_above_centre=review['real_above_centre'], known_clock=review['known_clock'],
        publication_rows=review['table_rows'], publication_checks=len(reports['review_audit1']['checks']),
        maximum_publication_relative_error=max(reports['review_audit1']['checks'].values()),
        figures_actually_viewed=['real_tail.png', 'known_transfer.png'],
        original_source_bindings=len(spec['sources']), original_input_bindings=len(spec['inputs']),
        original_conditional_source_bindings=151,
        original_failures_and_factors_untouched=True, factor_files_copied=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_default_driver_owned_takes_room_or_hearing_change=True,
        no_refit_or_later_four_fit_or_fitted_engine_loop=True,
        full_goal='ACTIVE: autonomous jointLR, V6fivebuses, multiple actual engines, all driving states and separate physical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = a.workspace/'baselines/locked_source_tail_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/locked_source_tail_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['locked_source_tail_v1', 'baselines/locked_source_tail_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known-first512/1024/2048 source-query diagnostic; allqueries/fullLRGrams/160rows independently verified',
        'Real weak tail persists;sourcefidelityFALSE;670C-H82voice3F2/index/hearings unchanged;no promotion',
        'research/源查询弱尾部与共同时间映射V1.md | research/locked_source_tail_v1_summary.json',
        'baselines/locked_source_tail_v1/validation.json'])
    print('TAIL_DIAGNOSTICS_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
