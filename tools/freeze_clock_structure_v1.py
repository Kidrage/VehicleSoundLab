"""Freeze known-first clock diagnosis and unchanged source/runtime contracts."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/clock_structure_v1'
    reports, sources, bound = {}, set(), {}
    for stage, result in (
        ('known1', 'clock_structure_known_measured'), ('known_audit1', 'independent_clock_structure_known_verified'),
        ('real1', 'clock_structure_real_measured'), ('audit1', 'independent_clock_structure_real_verified'),
        ('review1', 'clock_structure_review_published'), ('review_audit1', 'independent_clock_structure_review_verified'),
        ('bindings1', 'independent_clock_structure_bindings_verified')):
        row = load(evidence/stage/'report.json'); assert row['result'] == result
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
    assert not produced['original_source_fidelity_qualified'] and not produced['eligible_for_later_source_statistics']
    assert reports['known1']['known']['all_known_qualified']
    assert reports['bindings1']['verification_passed']
    for stage in ('known1', 'real1'):
        assert reports[stage]['capture_sha256'] == sha(evidence/stage/'capture.npz')
    for name, expected in review['figures'].items():
        assert sha(evidence/'review1'/name) == expected
    prior = a.workspace/'baselines/locked_source_tail_v1/evidence'
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/name); assert len(values) == count
        for relative, expected in values.items():
            assert sha(repo/relative) == expected
            sources.add(relative)
        save(evidence/name, values)
    previous = load(repo/'research/locked_source_tail_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == expected
    tail = load(Path(produced['tail_study'])/'real1/report.json')
    spec_path = Path(tail['source']['binding_file']); spec = load(spec_path)
    for name, expected in spec['sources'].items():
        assert sha(repo/name) == sha(spec_path.parent/'exact_sources'/name) == expected
    for name, expected in spec['inputs'].items():
        assert sha(name) == expected; bound[name] = expected
    conditional_file = a.workspace/'references/analysis/locked_source_diagnostics_followthrough_v1/manifest.json'
    conditional = load(conditional_file)
    assert conditional['run_spec_sha256'] == sha(spec_path) and len(conditional['source_sha256']) == 151
    for name, expected in conditional['source_sha256'].items():
        assert sha(name) == expected
        if Path(name).is_relative_to(repo):
            sources.add(Path(name).relative_to(repo).as_posix())
        else:
            assert Path(name).is_relative_to(a.workspace); bound[name] = expected
    bound[str(conditional_file)] = sha(conditional_file)
    assert load(spec_path.parent/'report.json')['result'] == 'failed'
    assert load(spec_path.parent/(produced['label']+'_audit')/'report.json')['result'] == 'failed'
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/共同相位映射台阶与受控声谱V1.md', 'research/locked_source_diagnostics_next_v1_plan.json',
        'research/clock_structure_next_v1_plan.json', 'tools/freeze_clock_structure_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, expected in bound.items():
        path = Path(name); assert sha(path) == expected
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='clock_structure_diagnostics_frozen',
        previous_goal_turn='progress: actual long-kernel weak-tail transfer diagnosis',
        this_goal_turn='progress: known-first controlled clocks, frozen observed-phase reconstruction, all-node signed curvature decomposition and independent full publication',
        actual_case=produced['label'], frames=produced['geometry']['query_frames'],
        fitted_orders_retained=288, fitted_nodes_retained=74, actual_clock_graph_nodes=22529,
        known_before_real=True, geometry=produced['geometry'],
        supplemental_control_and_frozen_provenance_bindings_verified=True,
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        original_virtual_highest_NRMSE=produced['old_source_highest_NRMSE'],
        controlled_above_centre=review['controlled_above_centre'],
        publication_node_rows=review['node_rows'], publication_curvature_rows=review['curvature_rows'],
        publication_numeric_values=reports['review_audit1']['numeric_values_checked'],
        maximum_publication_relative_error=reports['review_audit1']['maximum_relative_error'],
        figures_actually_viewed=['real_clock.png', 'controlled_transfer.png'],
        original_source_bindings=len(spec['sources']), original_input_bindings=len(spec['inputs']),
        original_conditional_source_bindings=151, original_failures_and_factors_untouched=True,
        factor_files_copied=False, protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_default_driver_owned_takes_room_or_hearing_change=True,
        no_actual_clock_target_change_or_refit_or_later_four_fits=True,
        full_goal='ACTIVE: autonomous jointLR, V6fivebuses, multiple actual engines, all driving states and separate physical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = a.workspace/'baselines/clock_structure_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/clock_structure_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['clock_structure_v1', 'baselines/clock_structure_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Frozen common-clock node/curvature decomposition and manufacturedC0/smooth transfer independently verified',
        'Clockcurvature is not acousticpower;sourcefidelityFALSE;670C-H82voice3F2/index/hearings unchanged',
        'research/共同相位映射台阶与受控声谱V1.md | research/clock_structure_v1_summary.json',
        'baselines/clock_structure_v1/validation.json'])
    print('CLOCK_STRUCTURE_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
