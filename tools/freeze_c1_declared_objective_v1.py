"""Freeze complete declared math proof separately from the retained SciPy failure."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/c1_declared_objective_v1'
    reports, sources, bound = {}, set(), {}
    expected = dict(known1='independent_c1_declared_known_verified',
        real1='independent_c1_declared_real_preparation_verified',
        resources1='c1_declared_single_input_preflight_verified')
    for stage, result in expected.items():
        r = load(evidence/stage/'report.json')
        assert r['result'] == result
        reports[stage] = r
        for name, value in r['sources'].items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == value
            sources.add(name)
        for name, value in r['inputs'].items():
            assert sha(name) == value and Path(name).suffix != '.bin'
            bound[name] = value
    known, real, resources = (reports[k] for k in ('known1', 'real1', 'resources1'))
    assert known['verification_passed'] and known['all_qualified']
    assert len(known['cases']) == 4 and known['complete_augmented_QR_cases'] == 3
    assert len(known['invalid_rejections']) == 10
    assert real['inputs'][str(evidence/'known1/report.json')] == sha(evidence/'known1/report.json')
    assert resources['inputs'][str(evidence/'real1/report.json')] == sha(evidence/'real1/report.json')
    assert real['complete_declared_preparation_mathematics_passed']
    assert not real['original_SciPy_preparation_audit_passed']
    assert real['original_failed_report_preserved'] and real['no_packet_reprepare_or_mutation']
    assert real['source_fidelity_not_evaluated'] and not real['eligible_for_later_source_statistics']
    assert real['known_only_dense_limit_rejects_real']
    case, = real['cases']
    assert case['label'] == 'F3 Fifth First Late'
    equations = case['complete_equations']
    assert equations['full_shape'] == [661724, 84096]
    assert not equations['original_SciPy_reference_RHS_gate_passed']
    assert equations['original_SciPy_reference_RHS_error'] == 2.5585096571438003e-12
    failure_path = a.workspace/'references/analysis/c1_source_adapter_v1/prepare_audit1/report.json'
    failure = load(failure_path)
    assert failure['result'] == 'failed' and '2.5585096571438003e-12' in failure['error']
    assert resources['namespace_before'] == resources['namespace_after']
    assert resources['cross_drive_reservation_NOT_implemented'] and resources['fit_NOT_authorized_by_this_report']
    previous = load(repo/'research/c1_source_adapter_v1_summary.json')
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(a.workspace/'baselines/c1_source_adapter_v1/evidence'/name)
        assert len(values) == count
        for relative, value in values.items():
            assert sha(repo/relative) == value
            sources.add(relative)
        save(evidence/name, values)
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, value in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == value
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_declared_objective_v1').glob('*.py'))
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/C1完整数学核验V1.md', 'research/c1_declared_objective_v1_plan.json',
        'research/c1_declared_objective_next_v1_plan.json', 'research/locked_source_diagnostics_next_v1_plan.json',
        'tools/audit_c1_declared_known_v1.py', 'tools/audit_c1_declared_real_v1.py',
        'tools/inspect_c1_declared_resources_v1.py', 'tools/freeze_c1_declared_objective_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, value in bound.items():
        path = Path(name)
        assert sha(path) == value
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='c1_declared_complete_preparation_evidence_frozen',
        actual_completed_stages=list(expected), no_live_jobs=True,
        known_complete_cases=4, known_complete_augmented_QR_cases=3, known_corruption_rejections=10,
        known_maximum_QR_relative_coefficient_difference=max(c['independent_complete_QR_relative_coefficient_difference'] or 0 for c in known['cases']),
        known_maximum_equation_or_dense_error=max(v for c in known['cases'] for v in c['maximum_errors'].values()),
        measurement_identity='vsl.c1-declared-objective/1', real_complete_equations=equations,
        real_maximum_errors=real['maximum_errors'],
        real_complete_declared_preparation_mathematics_passed=True,
        original_SciPy_preparation_audit_passed=False,
        original_failed_report_sha256=sha(failure_path), original_failure_not_relabelled=True,
        source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
        no_real_fit_or_packet_reprepare=True, no_cross_drive_reservation_yet=True,
        single_case_resource_preflight=resources['resources'],
        independent_all_phase_and_file_arithmetic_verified=True,
        original124sources101inputs151conditionalbindings_verified=True,
        original_captures_factors_failures_untouched=True, original_real_factor_files_copied=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_defaults_driver_owned_takes_room_or_hearing_change=True,
        no_new_audio_or_timbre_acceptance=True,
        full_goal='ACTIVE: autonomous jointLR/naturalHF/multiple actual engines/all driving states/V6fivebuses/independentphysical7.1.4',
        next_plan='research/c1_declared_objective_next_v1_plan.json',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/c1_declared_objective_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/c1_declared_objective_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['c1_declared_objective_v1', 'baselines/c1_declared_objective_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known complete4/augmentedQR3 before SAME FirstLate declared complete equations; single-case resource preflight',
        'Original SciPy audit stillFAIL; no realfit/reservation/source fidelity/statistics/runtime promotion',
        'research/C1完整数学核验V1.md | research/c1_declared_objective_v1_summary.json',
        'baselines/c1_declared_objective_v1/validation.json'])
    print('C1_DECLARED_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
