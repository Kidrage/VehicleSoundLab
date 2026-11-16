"""Freeze C1 counterfactual, original failures and protected runtime identities."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/clock_c1_v1'
    reports, sources, bound = {}, set(), {}
    for stage, result in (
        ('known1', 'clock_c1_known_measured'), ('known_audit1', 'independent_clock_c1_known_verified'),
        ('real1', 'clock_c1_real_measured'), ('audit1', 'independent_clock_c1_real_verified'),
        ('review1', 'clock_c1_review_published'), ('review_audit1', 'independent_clock_c1_review_verified'),
        ('bindings2', 'independent_clock_c1_bindings_verified')):
        report = load(evidence/stage/'report.json'); assert report['result'] == result
        reports[stage] = report
        for name, expected in report.get('sources', {}).items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == expected
            sources.add(name)
        for name, expected in report.get('inputs', {}).items():
            assert sha(name) == expected and Path(name).suffix != '.bin'
            bound[name] = expected
    for stage, audit in (('known1', 'known_audit1'), ('real1', 'audit1'), ('review1', 'review_audit1')):
        assert reports[audit]['verification_passed']
        assert reports[audit]['producer_sha256'] == sha(evidence/stage/'report.json')
    real = reports['real1']; assert reports['bindings2']['verification_passed']
    assert load(evidence/'bindings1/report.json')['result'] == 'failed'
    assert not real['original_source_fidelity_qualified'] and not real['eligible_for_later_source_statistics']
    assert reports['known1']['all_known_qualified']
    assert real['capture_sha256'] == sha(evidence/'real1/capture.npz')
    for name, expected in reports['review1']['figures'].items():
        assert sha(evidence/'review1'/name) == expected
    prior_archive = a.workspace/'baselines/clock_structure_v1/evidence'
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior_archive/name); assert len(values) == count
        for relative, expected in values.items():
            assert sha(repo/relative) == expected; sources.add(relative)
        save(evidence/name, values)
    previous = load(repo/'research/clock_structure_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected
    tail = load(a.workspace/'references/analysis/locked_source_tail_v1/real1/report.json')
    spec_path = Path(tail['source']['binding_file']); spec = load(spec_path)
    assert len(spec['sources']) == 124 and len(spec['inputs']) == 101
    for name, expected in spec['sources'].items():
        assert sha(repo/name) == sha(spec_path.parent/'exact_sources'/name) == expected
    for name, expected in spec['inputs'].items():
        assert sha(name) == expected; bound[name] = expected
    conditional_file = a.workspace/'references/analysis/locked_source_diagnostics_followthrough_v1/manifest.json'
    conditional = load(conditional_file)
    assert conditional['run_spec_sha256'] == sha(spec_path) and len(conditional['source_sha256']) == 151
    for name, expected in conditional['source_sha256'].items():
        assert sha(name) == expected
        path = Path(name)
        if path.is_relative_to(repo):
            sources.add(path.relative_to(repo).as_posix())
        else:
            assert path.is_relative_to(a.workspace); bound[name] = expected
    bound[str(conditional_file)] = sha(conditional_file)
    assert load(spec_path.parent/'report.json')['result'] == 'failed'
    assert load(spec_path.parent/(real['label']+'_audit')/'report.json')['result'] == 'failed'
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/保留观测节点的C1时间映射V1.md', 'research/clock_c1_next_v1_plan.json',
        'research/locked_source_diagnostics_next_v1_plan.json', 'research/clock_structure_next_v1_plan.json',
        'tools/audit_clock_c1_bindings_v1.py', 'tools/audit_clock_c1_bindings_v2.py', 'tools/freeze_clock_c1_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, expected in bound.items():
        path = Path(name); assert sha(path) == expected
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='clock_c1_diagnostics_frozen', previous_goal_turn='MCPS-only: no synthesis progress',
        this_goal_turn='progress: independently qualified node-preserving C1, one real counterfactual, all bands/LR/MS/time and publication',
        actual_case=real['label'], known_before_real=True, geometry=real['geometry'],
        metrics=reports['bindings2']['metrics'], fitted_orders_retained=288, fitted_nodes_retained=74,
        first_bindings1_reduced_norm_binary_equality_failure_retained=True,
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        original_virtual_highest_NRMSE=real['original_highest_NRMSE'],
        publication_numeric_values=reports['review_audit1']['verified_numeric_values'],
        figures_actually_viewed=['clock.png', 'spectra_stereo.png'],
        original_source_bindings=124, original_input_bindings=101, original_conditional_source_bindings=151,
        original_failures_and_factors_untouched=True, factor_files_copied=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_default_driver_owned_takes_room_or_hearing_change=True,
        no_actual_clock_target_change_or_refit_or_later_four_fits=True,
        full_goal='ACTIVE: autonomous jointLR, V6fivebuses, multiple actual engines, all driving states and separate physical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = a.workspace/'baselines/clock_c1_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/clock_c1_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['clock_c1_v1', 'baselines/clock_c1_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Node-preserving C1 known-first + one real diagnostic; every query/kernel/LR/MS/time independently checked',
        'No naturalness/source admission; originalfidelityFALSE;670C-H82voice3F2/index/hearings unchanged',
        'research/保留观测节点的C1时间映射V1.md | research/clock_c1_v1_summary.json',
        'baselines/clock_c1_v1/validation.json'])
    print('C1_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
