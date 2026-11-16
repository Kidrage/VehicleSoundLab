"""Freeze explicit source-input proofs, including the unresolved objective failure."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/c1_source_adapter_v1'
    reports, sources, bound = {}, set(), {}
    expected = dict(known1='c1_source_known_measured', known_audit1='independent_c1_source_known_verified',
        sampling_known1='c1_sampling_known_measured', sampling_known_audit1='independent_c1_sampling_known_verified',
        prepare1='c1_source_one_real_prepared', prepare_audit1='failed',
        rhs_diagnosis1='c1_preparation_RHS_rounding_diagnosed',
        input_audit1='independent_c1_source_input_only_verified',
        review1='c1_source_preparation_bandwidth_published', review_audit1='independent_c1_source_preparation_review_verified')
    for stage, result in expected.items():
        report = load(evidence/stage/'report.json'); assert report['result'] == result; reports[stage] = report
        for name, value in report.get('sources', {}).items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == value
            sources.add(name)
        for path, value in report.get('inputs', {}).items():
            assert sha(path) == value and Path(path).suffix != '.bin'
            bound[path] = value
    for study, audit in (('known1', 'known_audit1'), ('sampling_known1', 'sampling_known_audit1'), ('review1', 'review_audit1')):
        assert reports[audit]['verification_passed'] and reports[audit]['producer_sha256'] == sha(evidence/study/'report.json')
    assert reports['known1']['all_qualified'] and reports['known_audit1']['all_qualified']
    assert reports['sampling_known1']['all_qualified'] and reports['sampling_known_audit1']['all_qualified']
    failure = reports['prepare_audit1']
    assert failure['producer_sha256'] == sha(evidence/'prepare1/report.json')
    assert "'full_RHS'" in failure['error'] and '2.5585096571438003e-12' in failure['error']
    assert reports['input_audit1']['input_verification_passed'] and not reports['input_audit1']['full_objective_verification_passed']
    diagnosis = reports['rhs_diagnosis1']
    assert not diagnosis['original_cross_operator_gate_passed'] and diagnosis['declared_frozen_RHS_bitwise_identical_all_five']
    assert diagnosis['complete_preparation_audit_not_repaired'] and not diagnosis['certified_crossFFT_bound']
    for name, value in reports['review1']['figures'].items(): assert sha(evidence/'review1'/name) == value
    previous = load(repo/'research/clock_native_bridge_v1_summary.json')
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(a.workspace/'baselines/clock_native_bridge_v1/evidence'/name); assert len(values) == count
        for relative, value in values.items(): assert sha(repo/relative) == value; sources.add(relative)
        save(evidence/name, values)
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, value in previous['protected_hearings_sha256'].items(): assert sha(repo/name) == value
    prep = reports['prepare1']; row = prep['cases'][0]
    assert row['label'] == 'F3 Fifth First Late' and len(prep['cases']) == 1
    assert (row['frames'], row['target_frames'], row['orders'], row['nodes']) == (18430, 14334, 288, 73)
    assert load(evidence/'prepare1/protected_before.json') == load(evidence/'prepare1/protected_after.json')
    for path in (repo/'tools').glob('*c1_source*.py'): sources.add(path.relative_to(repo).as_posix())
    for path in (repo/'tools').glob('*c1_sampling*.py'): sources.add(path.relative_to(repo).as_posix())
    for folder in ('c1_source_adapter_v1', 'c1_source_prepare_v1'):
        sources.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/C1新声源输入与带宽V1.md', 'research/c1_source_adapter_v1_plan.json',
        'research/c1_source_preparation_v1_plan.json', 'research/c1_source_adapter_next_v1_plan.json',
        'research/locked_source_diagnostics_next_v1_plan.json', 'tools/diagnose_c1_preparation_rhs_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, value in bound.items():
        path = Path(name); assert sha(path) == value
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='c1_source_input_evidence_frozen',
        previous_goal_turn='MCPS-only verification, no synthesis progress',
        this_goal_turn='progress: known complete objective/QR and22k sampling proofs before ONE real explicit source input; failed full-objective audit diagnosed, physical bandwidth independently published',
        known_complete_cases=4, known_physical_sampling_cases=4,
        maximum_known_QR_relative_coefficient_difference=max(c['independent_QR_relative_coefficient_difference'] or 0 for c in reports['known_audit1']['cases']),
        maximum_known_analytic_sampling_relative_source_L1=reports['sampling_known_audit1']['maximum_errors']['analytic_sampling_accuracy'],
        actual_label=row['label'], frames=18430, target_frames=14334, orders=288, nodes=73,
        actual_input_geometry=reports['input_audit1']['geometry'],
        actual_input_sampling_errors=reports['input_audit1']['maximum_errors'], bandwidth=row['metadata']['bandwidth'],
        input_only_verification_passed=True, original_complete_preparation_audit_passed=False,
        complete_preparation_failure=failure['error'], RHS_diagnosis=diagnosis['cases'][-1],
        original_failure_not_relabelled=True, source_fidelity_not_evaluated=True,
        eligible_for_later_source_statistics=False, no_real_fit_launched=True,
        original124sources101inputs151conditionalbindings_verified=True,
        original_captures_factors_failures_untouched=True, original_real_factor_files_copied=False,
        physical_native_frames=reports['review1']['physical_native_frames'], physical_bandwidth_metrics=reports['review1']['metrics'],
        publication_numeric_values=reports['review_audit1']['published_numeric_values'],
        figures_actually_viewed=['source_bandwidth.png'],
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_defaults_driver_owned_takes_room_or_hearing_change=True,
        full_goal='ACTIVE: autonomous jointLR/naturalHF/multiple actual engines/all driving states/V6fivebuses/independentphysical7.1.4',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/c1_source_adapter_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/c1_source_adapter_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['c1_source_adapter_v1', 'baselines/c1_source_adapter_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known complete C1 objective/QR and22k sampling before one FirstLate source input; independent native bandwidth',
        'Full real objective audit FAIL at RHS2.5585e-12; diagnosed not repaired; no fit or runtime promotion',
        'research/C1新声源输入与带宽V1.md | research/c1_source_adapter_v1_summary.json',
        'baselines/c1_source_adapter_v1/validation.json'])
    print('C1_SOURCE_FROZEN', receipt, flush=True)


if __name__ == '__main__': main()
