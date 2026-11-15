"""Freeze same-case signed error diagnostics and unchanged runtime contracts."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/locked_source_error_v1'
    reports, sources, bound = {}, set(), {}
    for name, result in (
        ('real1', 'locked_source_native_error_budget_measured'),
        ('audit1', 'independent_locked_source_native_error_budget_verified'),
        ('review1', 'locked_source_error_assessment_published'),
        ('review_audit1', 'independent_locked_source_error_assessment_verified')):
        row = load(evidence/name/'report.json')
        assert row['result'] == result
        reports[name] = row
        for relative, expected in row.get('sources', {}).items():
            assert sha(repo/relative) == sha(evidence/name/'exact_sources'/relative) == expected
            sources.add(relative)
        for path, expected in row.get('inputs', {}).items():
            assert sha(path) == expected and Path(path).suffix != '.bin'
            bound[path] = expected
    produced, audit = reports['real1'], reports['audit1']
    review, ra = reports['review1'], reports['review_audit1']
    assert audit['verification_passed'] and audit['producer_sha256'] == sha(evidence/'real1/report.json')
    assert ra['verification_passed'] and ra['producer_sha256'] == sha(evidence/'review1/report.json')
    assert ra['all_bins_all_LR_all_four_variants_and_six_pairwise_sensitivities']
    assert len(produced['variants']) == len(audit['variants']) == len(review['physical']) == 4
    assert len(review['sensitivity']) == 6
    assert not produced['source_fidelity_qualified'] and not produced['eligible_for_later_source_statistics']
    assert produced['source_solver_qualified'] and produced['native16_32_convergence_passed']
    assert not review['source_fidelity_qualified'] and review['source_fidelity_gate_unchanged'] == .02
    for row in produced['variants']:
        assert sha(evidence/'real1'/row['file']) == row['sha256']
    for group in ('arrays', 'figures'):
        for name, expected in review[group].items():
            assert sha(evidence/'review1'/name) == expected
    prior = a.workspace/'baselines/locked_source_guard_v1/evidence'
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/name)
        assert len(values) == count
        for relative, expected in values.items():
            assert sha(repo/relative) == expected
            sources.add(relative)
        save(evidence/name, values)
    previous = load(repo/'research/locked_source_guard_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected
    case = Path(produced['source']['binding_file']).parent/produced['source']['label']
    spec = load(case.parent/'run_spec.json')
    for name, expected in spec['sources'].items():
        assert sha(repo/name) == sha(case.parent/'exact_sources'/name) == expected
    for path, expected in spec['inputs'].items():
        assert sha(path) == expected
        bound[path] = expected
    assert load(case.parent/'report.json')['result'] == 'failed'
    assert load(case.parent/(case.name+'_audit')/'report.json')['result'] == 'failed'
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/新声源误差分解与弱尾部V1.md', 'research/locked_source_diagnostics_next_v1_plan.json',
        'research/locked_source_error_v1_plan.json', 'tools/freeze_locked_source_error_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools/locked_source_error_v1').glob('*.py'))
    inputs = {}
    for name, expected in bound.items():
        path = Path(name)
        assert sha(path) == expected
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='locked_source_error_diagnostics_frozen',
        previous_goal_turn='progress: actual complete guard and five native/virtual diagnostics',
        this_goal_turn='progress: actual same-source four-component signed budget, virtual tail localization and independent publication audit',
        actual_case=case.name, full_orders=288, nodes=74, physical_variants=4, pairwise_sensitivities=6,
        reused_unchanged_core_known_before_real=True, declared_observer_known_before_real=True,
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        original_virtual_highest_NRMSE=review['original_target_NRMSE'][-1],
        above_centre_reference_fraction=review['virtual']['above_centre_reference_fraction_of_highest_weighted_mass'],
        above_centre_error_fraction=review['virtual']['above_centre_error_fraction_of_highest_weighted_mass'],
        maximum_main_component_sensitivity=max(value for row in review['sensitivity']
            for band in row['combined_component_band_NRMSE_relative_raw'][:5] for value in band),
        publication_checks=len(ra['checks']), maximum_publication_error=max(ra['checks'].values()),
        figures_actually_viewed=['physical_budget.png', 'virtual_split.png'],
        original_source_bindings=len(spec['sources']), original_input_bindings=len(spec['inputs']),
        original_failures_and_factors_untouched=True, factor_files_copied=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_default_driver_owned_takes_room_or_hearing_change=True,
        no_refit_or_later_four_fit_or_fitted_engine_loop=True,
        full_goal='ACTIVE: autonomous jointLR, V6fivebuses, multiple actual engines, all driving states and separate physical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = a.workspace/'baselines/locked_source_error_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/locked_source_error_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['locked_source_error_v1', 'baselines/locked_source_error_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Same-source four signed components, four variants and six sensitivity pairs independently verified',
        'Source fidelity FALSE;670C-H82voice3F2/index/hearings unchanged; no source/C promotion',
        'research/新声源误差分解与弱尾部V1.md | research/locked_source_error_v1_summary.json',
        'baselines/locked_source_error_v1/validation.json'])
    print('LOCKED_SOURCE_ERROR_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
