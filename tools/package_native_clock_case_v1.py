"""Freeze terminal audit controls, failures and pending real-case interfaces."""
import argparse
from pathlib import Path
import shutil
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace / 'references/analysis/native_clock_case_v1'
    folders = ('controls1', 'controls2', 'controls3', 'controls4', 'roundoff1', 'roundoff2')
    reports = {name: load(e / name / 'report.json') for name in folders}
    assert all(reports[name]['result'] == 'failed' for name in folders[:3])
    good = reports['controls4']
    assert good['all_controls_passed'] and len(good['cases']) == 19
    assert good['analytic_controls'] == 13 and good['actual_raw_interval_controls'] == 6
    full = a.workspace / 'baselines/waveform_file_full_v1'
    sources, inputs, locations, versions = set(), {}, {}, {}
    for file, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        protected = load(full / 'evidence' / file)
        assert len(protected) == count and all(sha(repo / name) == digest for name, digest in protected.items())
        sources.update(protected)
        save(e / file, protected)
    hearings = load(repo / 'research/waveform_file_full_v1_summary.json')['protected_hearings_sha256']
    assert all(sha(repo / name) == digest for name, digest in hearings.items())
    sources.update(hearings)

    def bind(name, digest):
        path = Path(name)
        assert sha(path) == digest, name
        if path.is_relative_to(e):
            target = 'evidence/' + path.relative_to(e).as_posix()
        else:
            assert path.is_relative_to(a.workspace)
            live = a.workspace / 'references/analysis/waveform_file_real_v1/real1'
            if path.is_relative_to(live):
                assert path == live / 'run_spec.json'
            leaf = 'external/' + path.relative_to(a.workspace).as_posix()
            inputs[leaf] = path
            target = 'inputs/' + leaf
        locations[str(path)] = target

    for folder, report in reports.items():
        for name, digest in report.get('inputs', {}).items():
            bind(name, digest)
        for name, digest in report.get('sources', {}).items():
            assert sha(e / folder / 'exact_sources' / name) == digest
            sources.add(name)
            versions.setdefault(name, {})[folder] = digest
    # roundoff was an explicitly separate diagnostic, not a new pass record.
    roundoff = reports['roundoff1']
    bind(roundoff['source'], roundoff['source_sha256'])
    assert not roundoff['normalized_cross_FFT_all_qualified']
    assert roundoff['failed_attempt_report_sha256'] == sha(e / 'controls3/report.json')
    live_spec = a.workspace / 'references/analysis/waveform_file_real_v1/real1/run_spec.json'
    spec = load(live_spec)
    assert len(spec['sources']) == 96 and len(spec['inputs']) == 71
    assert all(sha(repo / name) == digest for name, digest in spec['sources'].items())
    assert all(sha(name) == digest for name, digest in spec['inputs'].items())
    bind(live_spec, sha(live_spec))
    bind(full / 'manifest.json', sha(full / 'manifest.json'))
    prior = a.workspace / 'baselines/native_clock_render_v1/manifest.json'
    bind(prior, sha(prior))
    for directory in ('native_clock_case_v1', 'native_clock_case_audit_v1'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo / 'tools' / directory).glob('*.py'))
    sources.update(('tools/package_native_clock_case_v1.py', 'tools/verify_native_clock_case_bindings_v1.py',
        'tools/research_archive_v1.py', 'tools/verify_research_archive_independent_v1.py',
        'tools/run_native_clock_case_v1.py', 'tools/audit_native_clock_case_v1.py',
        'tools/run_native_clock_case_controls_v1.py', 'tools/diagnose_native_clock_case_roundoff_v1.py',
        'research/native_clock_case_v1_plan.json',
        'research/native_clock_case_next_v1_plan.json', 'research/真实原生渲染消费与复核V1.md',
        'README.md', 'AGENTS.md', 'handoff/C文件索引.csv', 'handoff/当前代码阅读入口.md',
        'handoff/研究续接.md', 'handoff/开发留痕.md', 'handoff/ADI21569算力复估V12.md'))
    inputs['data_AGENTS.md'] = a.workspace / 'AGENTS.md'
    shutil.copy2(__file__, e / 'executed_package.py')
    metadata = dict(result='native_clock_case_interfaces_and_audit_controls_frozen',
        selected_terminal_evidence_directories=list(folders), original_input_archive_locations=locations,
        executed_source_versions=versions, current_source_sha256={name: sha(repo / name) for name in sources},
        protected_hearings_sha256=hearings, analytic_controls=13, actual_raw_interval_controls=6,
        retained_failed_control_attempts=3, all_audit_equation_controls_passed=True,
        actual_terminal_fit_admission_exercised=False, actual_fitted_native_render_qualified=False,
        protected_run_spec_sources=96, protected_run_spec_inputs=71,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True,
        no_active_factors_or_terminal_capture_archived=True,
        real_job_observation=load(e / 'real_job_observation.json'),
        previous_goal_turn_classification='No synthesis progress: MCPS-only recheck. Current stage is consumer implementation and qualified audit equations.',
        no_C_or_default_or_hearing_or_sustained_voice_promotion=True, full_goal='active')
    root = a.workspace / 'baselines/native_clock_case_v1'
    summary = freeze(root, repo, sources, e, inputs, metadata)
    save(repo / 'research/native_clock_case_v1_summary.json', dict(metadata, **summary))
    append_index(repo / 'handoff/阶段索引.csv', ['native_clock_case_v1', 'baselines/native_clock_case_v1/manifest.json',
        summary['file_count'], summary['manifest_sha256'],
        'Actual terminal native consumer implemented;13analytic+6raw audit controls PASS;3failures retained',
        '670C-H82voice3F2/index/hearings exact;actual terminal admission/native fit NOTyet qualified',
        'research/真实原生渲染消费与复核V1.md | research/native_clock_case_v1_summary.json',
        'baselines/native_clock_case_v1/validation.json'])
    print(summary, flush=True)


if __name__ == '__main__':
    main()
