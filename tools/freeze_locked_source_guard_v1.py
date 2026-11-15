"""Freeze terminal math/virtual/native diagnostics without copying factor files."""
import argparse
from pathlib import Path
import shutil
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--staging', type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    guard = a.workspace / 'references/analysis/locked_source_guard_v1'
    diagnostic = a.workspace / 'references/analysis/locked_source_diagnostics_v1'
    staging = a.staging or a.workspace / 'references/analysis/locked_source_guard_archive_v1'
    staging.mkdir(parents=True, exist_ok=False)
    sources, bound, reports = set(), {}, {}
    packing_failure = a.workspace / 'references/analysis/locked_source_guard_archive_v1/packing_failure_receipt.json'
    if packing_failure.exists():
        assert load(packing_failure)['result'] == 'archive_preparation_failed'
        bound[str(packing_failure)] = sha(packing_failure)
        shutil.copy2(packing_failure, staging / packing_failure.name)
    expected = {
        'measurement1': 'independent_locked_saved_wave_measurement_controls_verified',
        'known1': 'failed', 'known2': 'independent_locked_source_guard_known_verified',
        'real1': 'independent_locked_source_real_verified',
        'review1': 'locked_source_terminal_diagnostics_reviewed',
        'review_audit1': 'independent_locked_source_review_verified',
    }
    for name, result in expected.items():
        info = load(guard / name / 'report.json')
        assert info['result'] == result
        reports[name] = info
        shutil.copytree(guard / name, staging / 'guard' / name)
    expected_diagnostics = {
        'virtual_real1': 'locked_source_real_virtual_measured',
        'virtual_real_audit1': 'independent_locked_source_virtual_verified',
        'virtual_real_stereo_audit1': 'independent_locked_source_virtual_stereo_verified',
        'native_real1': 'locked_source_native_case_measured',
        'native_real_audit1': 'independent_locked_source_native_verified',
    }
    for name, result in expected_diagnostics.items():
        info = load(diagnostic / name / 'report.json')
        assert info['result'] == result
        reports[name] = info
        shutil.copytree(diagnostic / name, staging / 'diagnostics' / name)
    historical_source_differences = []
    # A retained failed attempt may have an older executed checker. Verify its
    # own immutable snapshot, rather than pretending it used today's source.
    for path in staging.rglob('report.json'):
        info = load(path)
        for name, digest in info.get('sources', {}).items():
            if sha(repo / name) == digest:
                sources.add(name)
            else:
                assert info['result'] == 'failed', name
                assert sha(path.parent / 'exact_sources' / name) == digest, name
                historical_source_differences.append(dict(report=path.relative_to(staging).as_posix(),
                    source=name, executed_sha256=digest, current_sha256=sha(repo / name)))
        for name, digest in info.get('inputs', {}).items():
            assert sha(name) == digest, name
            assert Path(name).suffix != '.bin'
            bound[name] = digest
    math = reports['real1']
    assert math['verification_passed'] and not math['all_qualified']
    assert math['case']['solver_qualified'] and not math['case']['fidelity_qualified']
    assert math['case']['file_resource_audit']['all_qualified']
    assert not math['case']['retained_cross_operator_metric_comparison']['original_2e_12_comparison_passed']
    assert math['case']['declared_saved_wave_metric_comparison']['original_2e_12_comparison_passed']
    assert reports['known2']['all_qualified'] and len(reports['known2']['invalid_rejections']) == 5
    assert reports['measurement1']['all_qualified']
    assert reports['review_audit1']['verification_passed']
    native = reports['native_real_audit1']
    assert native['verification_passed'] and native['native16_32_convergence_passed']
    assert not native['source_fidelity_qualified'] and not native['eligible_for_later_source_statistics']
    case = Path(reports['native_real1']['paths']['case'])
    spec = load(case.parent / 'run_spec.json')
    for name, digest in spec['sources'].items():
        assert sha(repo / name) == sha(case.parent / 'exact_sources' / name) == digest
    for name, digest in spec['inputs'].items():
        assert sha(name) == digest
        bound[name] = digest
    for name in ('run_spec.json', 'report.json'):
        assert name != 'report.json' or load(case.parent / name)['result'] == 'failed'
        path = case.parent / name
        shutil.copy2(path, staging / ('original_' + name))
    shutil.copytree(case.parent / (case.name + '_audit'), staging / 'original_failed_audit')
    for name in ('report.json', 'capture.npz'):
        path = case / name
        target = staging / 'original_case' / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path, target)
    prior = a.workspace / 'baselines/locked_source_adapter_v1/evidence'
    for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior / filename)
        assert len(values) == count
        for name, digest in values.items():
            assert sha(repo / name) == digest
            sources.add(name)
        save(staging / filename, values)
    prior_summary = load(repo / 'research/locked_source_adapter_v1_summary.json')
    assert sha(repo / 'handoff/C文件索引.csv') == prior_summary['protected_C_index_sha256']
    for name, digest in prior_summary['protected_hearings_sha256'].items():
        assert sha(repo / name) == digest
    sources.update({
        'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/新声源数学核验与真实声场诊断V1.md', 'research/locked_source_diagnostics_next_v1_plan.json',
        'tools/freeze_locked_source_guard_v1.py', 'tools/verify_research_archive_independent_v1.py',
    })
    inputs = {}
    for name, digest in bound.items():
        path = Path(name)
        assert sha(path) == digest and path.suffix != '.bin'
        if path.is_relative_to(a.workspace):
            key = 'workspace/' + path.relative_to(a.workspace).as_posix()
        else:
            assert path.is_relative_to(repo)
            key = 'repository/' + path.relative_to(repo).as_posix()
        inputs[key] = path
    validation = dict(result='locked_source_terminal_guard_evidence_frozen',
        previous_goal_turn='MCPS-only: no synthesis progress',
        this_goal_turn='progress: actual complete math verification, all five real diagnostics and independently checked publication',
        measurement_controls_passed=True, nonzero_controls=3, corrupt_capture_rejections=5,
        actual_math_verified=True, source_solver_qualified=True, source_fidelity_qualified=False,
        cross_operator_comparison_failure_retained=True, original_terminal_failures_retained=True,
        actual_five_diagnostic_stages_complete=True, native16_32_convergence_passed=True,
        eligible_for_later_source_statistics=False, publication_checked_values=reports['review_audit1']['checked_values'],
        figures_visually_inspected=['all_bands.png', '0_14k.png'],
        original_source_bindings=len(spec['sources']), original_input_bindings=len(spec['inputs']),
        factor_files_copied=False, original_fit_or_coordinator_restarted=False,
        retained_failed_attempt_source_versions=historical_source_differences,
        protected_C_index_sha256=sha(repo / 'handoff/C文件索引.csv'),
        protected_hearings_sha256=prior_summary['protected_hearings_sha256'],
        no_C_default_or_sustained_or_hearing_promotion=True,
        full_goal='ACTIVE: V6 five buses, autonomous joint LR, multiple engines, full driving states and separate physical7.1.4',
        input_archive_locations={str(path): name for name, path in inputs.items()})
    root = a.workspace / 'baselines/locked_source_guard_v1'
    receipt = freeze(root, repo, sources, staging, inputs, validation)
    save(repo / 'research/locked_source_guard_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo / 'handoff/阶段索引.csv', ['locked_source_guard_v1', 'baselines/locked_source_guard_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Complete independent math and actual five virtual/native diagnostics; source fidelity FALSE retained',
        '670C-H82voice3F2/index/hearings unchanged; no fitted engine loops or C promotion',
        'research/新声源数学核验与真实声场诊断V1.md | research/locked_source_guard_v1_summary.json',
        'baselines/locked_source_guard_v1/validation.json'])
    print('LOCKED_GUARD_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
