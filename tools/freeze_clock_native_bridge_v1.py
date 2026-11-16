"""Freeze native bridge diagnostics and independently bound runtime contracts."""
import argparse
import csv
import math
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/clock_native_bridge_v1'
    reports, sources, bound = {}, set(), {}
    for stage, result in (
        ('known1', 'clock_native_bridge_known_measured'),
        ('known_audit1', 'independent_clock_native_bridge_known_verified'),
        ('known_bindings1', 'independent_clock_native_bridge_bindings_verified'),
        ('real1', 'clock_native_bridge_real_measured'),
        ('audit1', 'independent_clock_native_bridge_real_verified'),
        ('bindings1', 'independent_clock_native_bridge_bindings_verified'),
        ('review1', 'clock_native_bridge_review_published'),
        ('review_audit1', 'independent_clock_native_bridge_review_verified')):
        report = load(evidence/stage/'report.json'); assert report['result'] == result
        reports[stage] = report
        for name, expected in report.get('sources', {}).items():
            assert sha(repo/name) == sha(evidence/stage/'exact_sources'/name) == expected
            sources.add(name)
        for name, expected in report.get('inputs', {}).items():
            assert sha(name) == expected and Path(name).suffix != '.bin'
            bound[name] = expected
    for stage, audit in (('known1', 'known_audit1'), ('known1', 'known_bindings1'),
        ('real1', 'audit1'), ('real1', 'bindings1'), ('review1', 'review_audit1')):
        assert reports[audit]['verification_passed']
        assert reports[audit]['producer_sha256'] == sha(evidence/stage/'report.json')
    assert reports['known1']['all_known_qualified'] and reports['known_audit1']['all_known_qualified']
    real = reports['real1']
    assert not real['original_source_fidelity_qualified'] and not real['eligible_for_later_source_statistics']
    assert isinstance(real['C1_native16_32_converged'], bool) and isinstance(real['PL_native16_32_converged'], bool)
    for name, expected in reports['review1']['figures'].items(): assert sha(evidence/'review1'/name) == expected
    for name, expected in real['files'].items(): assert sha(evidence/'real1'/name) == expected
    prior = a.workspace/'baselines/clock_c1_v1/evidence'
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(prior/name); assert len(values) == count
        for relative, expected in values.items(): assert sha(repo/relative) == expected; sources.add(relative)
        save(evidence/name, values)
    previous = load(repo/'research/clock_c1_v1_summary.json')
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, expected in previous['protected_hearings_sha256'].items(): assert sha(repo/name) == expected
    tail = load(a.workspace/'references/analysis/locked_source_tail_v1/real1/report.json')
    spec_path = Path(tail['source']['binding_file']); spec = load(spec_path)
    assert len(spec['sources']) == 124 and len(spec['inputs']) == 101
    for name, expected in spec['sources'].items():
        assert sha(repo/name) == sha(spec_path.parent/'exact_sources'/name) == expected
    for name, expected in spec['inputs'].items(): assert sha(name) == expected; bound[name] = expected
    conditional_file = a.workspace/'references/analysis/locked_source_diagnostics_followthrough_v1/manifest.json'
    conditional = load(conditional_file)
    assert conditional['run_spec_sha256'] == sha(spec_path) and len(conditional['source_sha256']) == 151
    for name, expected in conditional['source_sha256'].items():
        assert sha(name) == expected
        path = Path(name)
        if path.is_relative_to(repo): sources.add(path.relative_to(repo).as_posix())
        else: assert path.is_relative_to(a.workspace); bound[name] = expected
    bound[str(conditional_file)] = sha(conditional_file)
    assert load(spec_path.parent/'report.json')['result'] == 'failed'
    assert load(spec_path.parent/(real['label']+'_audit')/'report.json')['result'] == 'failed'
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/C1时间映射与原生重建V1.md', 'research/clock_native_bridge_next_v1_plan.json',
        'research/locked_source_diagnostics_next_v1_plan.json', 'research/clock_c1_next_v1_plan.json',
        'tools/audit_clock_native_bridge_bindings_v1.py', 'tools/freeze_clock_native_bridge_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    for name, expected in bound.items():
        path = Path(name); assert sha(path) == expected
        prefix, base = ('workspace', a.workspace) if path.is_relative_to(a.workspace) else ('repository', repo)
        assert path.is_relative_to(base)
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    comparisons = real['comparisons']
    c = comparisons['C1_32_vs_FIR_only']['signed_changes']['broad']
    with (evidence/'review1/bands.csv').open(encoding='utf-8', newline='') as f:
        bands = {(v['signal'], v['physical_band_Hz']):v for v in csv.DictReader(f)}
    upper = lambda name:sum(float(bands[(name, '14-24k')][key]) for key in ('L_FS2', 'R_FS2'))
    metrics = dict(
        C1_32_vs_source_FIR_wave_NRMSE=comparisons['C1_32_vs_FIR_only']['wave_NRMSE'],
        C1_32_vs_source_FIR_0_14k_max_power_change_dB=max(abs(v) for row in c['power_change_dB'][:5] for v in row),
        C1_32_vs_source_FIR_0_14k_max_complex_coherence_change=max(math.hypot(*v) for v in c['complex_coherence_change'][:5]),
        C1_32_vs_source_FIR_0_14k_max_CV_change=max(abs(v) for row in c['CV_change'][:5] for v in row),
        C1_16_vs_32_wave_NRMSE=comparisons['C1_16_vs_C1_32']['wave_NRMSE'],
        C1_16_vs_32_max_band_NRMSE=max(comparisons['C1_16_vs_C1_32']['band_complex_NRMSE']),
        source_FIR_14_24k_LR_power_change_from_raw_dB=10*math.log10(upper('FIR_only')/upper('raw')),
        C1_32_vs_raw_14_24k_complex_NRMSE=comparisons['C1_32_vs_raw']['band_complex_NRMSE'][-1])
    validation = dict(result='clock_native_bridge_diagnostics_frozen', previous_goal_turn='MCPS-only, no synthesis progress',
        this_goal_turn='progress: executed known-first supported C1 native48k bridge, independent all-query and physical LR/MS/time diagnostics',
        actual_case=real['label'], known_before_real=True, known_controls=22,
        known_separate_band_convergence_failures=[v['label'] for v in reports['known1']['cases'] if not v['native16_32_all_six_bands_converged']],
        native_frames=real['count'], native_start=real['native_start'], inverse_roundtrip=real['inverse_roundtrip'],
        C1_native16_32_converged=real['C1_native16_32_converged'], PL_native16_32_converged=real['PL_native16_32_converged'],
        physical_comparisons=comparisons, metrics=metrics, original_virtual_highest_NRMSE=real['original_highest_NRMSE'],
        original_source_fidelity_qualified=False, eligible_for_later_source_statistics=False,
        original_288orders_74nodes_18434sourcequeries_89clocknodes_unchanged=True,
        publication_numeric_values=reports['review_audit1']['verified_numeric_values'],
        figures_actually_viewed=['native_bridge.png', 'stereo_time.png'],
        original_source_bindings=124, original_input_bindings=101, original_conditional_source_bindings=151,
        original_failures_and_factors_untouched=True, factor_files_copied=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'], protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_default_driver_owned_takes_room_or_hearing_change=True,
        no_actual_clock_target_change_or_refit_or_later_four_fits=True,
        full_goal='ACTIVE: autonomous jointLR, V6 five buses, multiple actual engines/all driving states, independent physical7.1.4',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/clock_native_bridge_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/clock_native_bridge_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['clock_native_bridge_v1', 'baselines/clock_native_bridge_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known-first C1 native48k bridge; all-query inverse/reconstruction/FIR and all physical LR/MS/time checked',
        'Diagnostic only; originalfidelityFALSE; sparse known convergence failures retained;670C-H82voice3F2 unchanged',
        'research/C1时间映射与原生重建V1.md | research/clock_native_bridge_v1_summary.json',
        'baselines/clock_native_bridge_v1/validation.json'])
    print('BRIDGE_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
