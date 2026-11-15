"""Freeze all conditional-phase slope attempts and independently audited evidence."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = args.workspace/'references/analysis/conditional_phase_slope_v1'
    root = args.workspace/'baselines/conditional_phase_slope_v1'
    if args.verify:
        manifest = verify(root)
        print(dict(result='archive_verified', files=manifest['file_count'], bytes=manifest['bytes']))
        return
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np

    parent = args.workspace/'baselines/conditional_phase_feasibility_v1'
    parent_summary = load(repo/'research/conditional_phase_feasibility_v1_summary.json')
    assert sha(parent/'manifest.json') == parent_summary['manifest_sha256']
    entries = {r['path']: r['sha256'] for r in load(parent/'manifest.json')['files']}
    protected = {}
    for name, count in [('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)]:
        hashes = load(parent/'evidence'/name)
        assert len(hashes) == count and all(sha(repo/n) == h for n, h in hashes.items())
        save(evidence/name, hashes)
        protected[name] = hashes
    names = set()
    for command in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']]:
        names.update(subprocess.check_output(['git']+command, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(protected['C_files_sha256.json'])
    index = list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='')))
    assert len(index) == 671 and all(r[4] == protected['C_files_sha256.json'][r[0]] for r in index[1:])
    assert sha(repo/'handoff/C文件索引.csv') == entries['source/handoff/C文件索引.csv']
    for name, expected in entries.items():
        if name.startswith('source/research/') and ('listening' in name or 'acceptance' in name):
            assert sha(repo/name.removeprefix('source/')) == expected

    histories = {}
    for number in range(1, 6):
        known = load(evidence/f'known{number}/report.json')
        audit = load(evidence/f'known_audit{number}/report.json')
        assert known['result'] == 'conditional_slope_known_controls_ready' and len(known['cases']) == 8
        assert audit['result'] == 'independent_conditional_slope_audit_passed'
        assert audit['models'] == 6 and audit['LP_certificates'] == 12
        assert audit['producer_sha256'] == sha(evidence/f'known{number}/report.json')
        assert audit['auditor_sha256'] == sha(evidence/f'known_audit{number}/executed_audit.py')
        for n, h in known['sources'].items():
            assert sha(evidence/f'known{number}/exact_sources'/n) == h
            if number == 5:
                assert sha(repo/n) == h
        histories[f'known{number}'] = known['result']
        histories[f'known_audit{number}'] = audit['result']
    for number in range(1, 6):
        study = load(evidence/f'real{number}/report.json')
        assert study['result'] == ('failed' if number < 4 else 'six_source_conditional_slope_evidence_ready')
        for n, h in study['sources'].items():
            assert sha(evidence/f'real{number}/exact_sources'/n) == h
            if number == 5:
                assert sha(repo/n) == h
        for n, h in study['inputs'].items():
            assert sha(n) == h
        histories[f'real{number}'] = study['result']

    source = load(evidence/'real5/report.json')
    assert len(source['cases']) == 6 and all(len(r['harmonics']) == 288 for r in source['cases'])
    for row in source['cases']:
        for harmonic in row['harmonics']:
            suffix = Path(row['label'])/f'{harmonic["order"]:03d}'/'model.npz'
            assert sha(evidence/'real5'/suffix) == harmonic['sha256']
            with np.load(evidence/'real4'/suffix) as before, np.load(evidence/'real5'/suffix) as after:
                assert set(after.files) == set(before.files)|{'density_primal_dual_gap_raw_float64', 'variation_primal_dual_gap_raw_float64'}
                for name in before.files:
                    if name not in ('density_primal_dual_gap', 'variation_primal_dual_gap'):
                        assert np.array_equal(before[name], after[name]), (suffix, name)
                for stage in ('density', 'variation'):
                    assert np.array_equal(before[stage+'_primal_dual_gap'], after[stage+'_primal_dual_gap_raw_float64'])
    failed_audit = load(evidence/'real_audit1/report.json')
    assert failed_audit['result'] == 'failed'
    assert (evidence/'real_audit1/executed_audit.py').is_file()
    audit = load(evidence/'real_audit2/report.json')
    assert audit['result'] == 'independent_conditional_slope_audit_passed'
    assert audit['models'] == 1728 and audit['LP_certificates'] == 3456
    assert audit['all_source_summary_fields_verified']
    assert audit['declared_identical_1025_point_paths_verified']
    assert audit['producer_sha256'] == sha(evidence/'real5/report.json')
    assert audit['auditor_sha256'] == sha(repo/'tools/audit_conditional_phase_slope_v1.py')
    assert audit['auditor_sha256'] == sha(evidence/'real_audit2/executed_audit.py')
    assert sha(evidence/'real_audit1/executed_audit.py') != audit['auditor_sha256']
    precision = load(evidence/'numerical_precision_receipt.json')
    assert precision['final']['targets_changed'] is False
    assert precision['final']['original_physical_acceptance'] == 2e-7
    assert precision['matrix_precision_failure']['original_target_or_constraint_coefficients_changed'] is False
    assert precision['extra_cutoff_repair_176_completed_numeric_files_exact']
    assert precision['dual_accumulation_failure']['optimization_matrix_target_solver_changed'] is False
    for name in ('review1', 'review2'):
        review = load(evidence/name/'report.json')
        assert review['result'] == 'conditional_slope_figure_ready'
        for n, h in review['sources'].items():
            assert sha(evidence/name/'exact_sources'/n) == h
            if name == 'review2':
                assert sha(repo/n) == h
        for n, h in review['inputs'].items():
            assert sha(n) == h
        assert sha(evidence/name/'figure_inputs.json') == review['figure_inputs_sha256']
        for n, h in review['images'].items():
            assert sha(evidence/name/n) == h
    first_review = load(evidence/'review1/report.json')
    assert first_review['figure_inputs_sha256'] == review['figure_inputs_sha256']
    assert first_review['strict_floating_point_comparison_counts'] == review['strict_floating_point_comparison_counts']
    assert load(evidence/'review1/visual_review.json')['accepted_for_publication'] is False
    visual = load(evidence/'review2/visual_review.json')
    assert visual['scientific_figures_individually_viewed'] == 1 and visual['accepted_for_publication']
    assert visual['images_sha256'] == review['images']
    assert not list(evidence.rglob('*.wav'))

    harmonics = [h for row in source['cases'] for h in row['harmonics']]
    outcomes = dict(
        strict_floating_point_comparison_counts=review['strict_floating_point_comparison_counts'],
        maximum_cross_target_error={stage: max(h['stages'][stage]['cross_target_error'] for h in harmonics)
                                    for stage in ('parent', 'density', 'variation')},
        maximum_phase_marginal_error={stage: max(h['stages'][stage]['phase_marginal_error'] for h in harmonics)
                                      for stage in ('parent', 'density', 'variation')},
        maximum_24_band_change_from_parent={stage: max(
            abs(complex(*band[stage])-complex(*band['parent'])) for row in source['cases'] for band in row['bands'])
            for stage in ('density', 'variation')},
        maximum_absolute_certificate_gap={stage: max(abs(h['stages'][stage]['primal_dual_gap']) for h in harmonics)
                                           for stage in ('density', 'variation')},
        maximum_absolute_raw_float64_gap_diagnostic={stage: max(abs(h['stages'][stage]['primal_dual_gap_raw_float64']) for h in harmonics)
                                                     for stage in ('density', 'variation')},
        counts_are_strict_numeric_comparisons_not_audibility=True)
    save(evidence/'outcomes.json', outcomes)

    validation = dict(
        result='conditional_phase_slope_frozen',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        previous_goal_turn='Progress: real4 complete, independent audit found dual accumulation and signed-gap gate defects; repaired Decimal/absolute gate and exact Fraction audit, known5 passed, real5 launched. This turn continues the same live handle and final qualification.',
        known_controls=8, numerical_known_models=6, source_models=6, harmonics=1728,
        real_LP_certificates=3456, unitless_probe_points=1025,
        summary=source['summary'], outcomes=outcomes, audit=audit, retained_attempts=histories, precision_receipt=precision,
        all1728_LP_solutions_duals_maps_paths_exact_real4_to_real5=True,
        raw_float64_signed_gap_preserved_and_absolute_gate_fixed=True,
        producer_decimal_vs_independent_exact_binary_rational_gap=True,
        failed_real_audit1_and_both_exact_diagnostics_retained=True,
        same_parent_positive_probe_target_and_original_marginals=True,
        moment_component_interval=1e-9, unchanged_physical_acceptance=2e-7,
        no_actual_audio_time_law_or_naturalness_claim=True,
        scientific_figures_individually_viewed=1,
        review1_label_overlap_retained_review2_layout_only_data_exact=True,
        C_H_exact=670, voice_parameters_exact=82, F2_files_exact=3, C_index_exact=True,
        new_C_H=0, new_audio=False, runtime_default_driver_owned_take_room_changed=False,
        parent_and_old_F2_F3_hearings='independently pending; not repeated',
        old_68CTest_not_repeated=True, downloaded=False, pushed=False,
        physical_7_1_4=False, ADI_candidate_budget_claimed=False, full_goal='active',
        next='Validate actual generated time through the original observation window before audio/listening/C port; retain amplitude-joint feasibility gaps, all slope/path regressions, V6 buses, one driver and independent future spatial layer. Full multi-engine/state/physical7.1.4 remain incomplete.')
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])
    sources += [n for n in names if 'conditional_phase' in n and Path(n).suffix in ('.py', '.md', '.json')]
    sources += list(source['sources'])+[
        'tools/research_archive_v1.py', 'research/条件相位斜率优化V1.md',
        'research/relative_phase_v1_listening.json', 'research/relative_phase_v1_summary.json',
        'AGENTS.md', 'README.md', 'handoff/C文件索引.csv', 'handoff/开发留痕.md',
        'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
    shutil.copy2(__file__, evidence/'executed_package.py')
    inputs = dict(data_AGENTS=args.workspace/'AGENTS.md', parent_manifest=parent/'manifest.json',
                  parent_validation=parent/'validation.json',
                  frozen_C_build_source_zip=args.workspace/'baselines/F3_local_atlas_v1/source.zip')
    # Copy every frozen parent transport and amplitude input, not only its manifest.
    for name in source['inputs']:
        path = Path(name)
        if path.is_relative_to(parent):
            inputs['frozen_parent_inputs/'+path.relative_to(parent).as_posix()] = path
    result = freeze(root, repo, sources, evidence, inputs, validation)
    verify(root)
    save(repo/'research/conditional_phase_slope_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', [
        'conditional_phase_slope_v1', 'baselines/conditional_phase_slope_v1/manifest.json',
        result['file_count'], result['manifest_sha256'],
        '8known;6source1728models3456LPcertificates;independentCDF-duals-quadrature-path;1figure',
        '670C-H82voice3F2/index exact;same-target slope optimization;all regressions retained;no audio/C/hearing change',
        'research/条件相位斜率优化V1.md | research/conditional_phase_slope_v1_summary.json',
        'baselines/conditional_phase_slope_v1/validation.json'])
    print(result)


if __name__ == '__main__':
    main()
