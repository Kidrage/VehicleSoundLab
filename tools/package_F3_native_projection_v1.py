"""Freeze numeric support and the rejected independent-remainder interpretation."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    e = a.workspace/'references/analysis/F3_native_projection_v1'
    root = a.workspace/'baselines/F3_native_projection_v1'
    if a.verify:
        result = verify(root)
        print(dict(result='archive_verified', files=result['file_count'], bytes=result['bytes']))
        return
    m, audit, review = [load(e/name/'report.json') for name in ['measure1', 'audit3', 'review1']]
    assert m['result'] == 'native_harmonic_remainder_cross_budgets_measured'
    assert audit['result'] == 'independent_native_projection_audit_passed'
    assert review['result'] == 'native_projection_limits_plotted'
    assert audit['producer_report_sha256'] == review['producer_report_sha256'] == sha(e/'measure1/report.json')
    assert review['audit_report_sha256'] == sha(e/'audit3/report.json')
    assert len(m['known']) == 11 and len(m['cases']) == 6 and m['real_stereo_inputs'] == 60
    assert audit['stereo_inputs'] == 71 and audit['spectral_windows'] == 477
    assert audit['explicit_DFT_complex_values'] == 68688
    for name, h in m['sources'].items():
        assert sha(e/'measure1/exact_sources'/name) == sha(repo/name) == h
    for name, h in m['inputs'].items():
        assert sha(name) == h
    for name, h in m['protected_before'].items():
        assert sha(repo/name) == h
    failed = load(e/'audit1/report.json')
    assert failed['result'] == 'failed' and failed['error'] == 'AssertionError()' and len(failed['cases']) == 6
    for folder in ['audit2', 'audit3']:
        report = load(e/folder/'report.json')
        assert report['result'] == 'independent_native_projection_audit_passed'
        assert sha(e/folder/'executed_audit.py') == report['auditor_sha256']
    assert sha(repo/'tools/audit_F3_native_projection_v1.py') == sha(e/'audit3/executed_audit.py')
    assert sha(repo/'tools/review_F3_native_projection_v1.py') == sha(e/'review1/executed_review.py')
    assert load(e/'review1/visual_review.json')['two_scientific_figures_individually_viewed']
    for name, h in review['images'].items():
        assert sha(e/'review1'/name) == h
    for row in m['known']+[c[k] for c in m['cases'] for k in ['source', 'generated']]:
        assert sha(e/'measure1'/row['label']/'arrays.npz') == row['data_sha256']
        assert (e/'audit3'/(row['label']+'_cross_eigenvalues.npz')).is_file()
    prior = a.workspace/'baselines/catalog_local_F3_v1/evidence'
    c_files, voices = [load(prior/name) for name in ['C_files_sha256.json', 'voice_files_sha256.json']]
    assert len(c_files) == 667 and len(voices) == 82
    names = set()
    for flags in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']]:
        names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(c_files)
    index = list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='')))
    assert len(index) == 668 and all(row[4] == c_files[row[0]] for row in index[1:])
    inputs = {'data_AGENTS.md': a.workspace/'AGENTS.md'}
    parent = a.workspace/'baselines/F3_local_detail_budget_v1'
    inputs['parent_manifest.json'] = parent/'manifest.json'
    inputs['parent_measurement_report.json'] = parent/'evidence/measure1/report.json'
    for row in m['cases']:
        inputs[row['label']+'/coordinates.npz'] = Path(row['coordinate_input'])
        inputs[row['label']+'/measurement.npz'] = parent/'evidence/measure1'/row['label']/'measurement.npz'
    shutil.copy2(__file__, e/'executed_package.py')
    validation = dict(
        result='native_projection_numeric_pass_independent_remainder_target_not_qualified',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        previous_goal_turn='Progress: native stereo budget completed and archived; current turn executes known-controlled conditional decomposition and rejects direct remainder promotion.',
        runtime_C_H_exact=667, voice_parameters_exact=82, F2_exact=True,
        known_cases=11, source_stereo_inputs=6, C_stereo_inputs=54,
        all_stereo_inputs=71, all_windows=477, explicit_DFT_complex_values=68688,
        max_wave_difference_FS=audit['max_wave_difference_FS'],
        max_matrix_difference_FS2=audit['max_spectral_difference_FS2'],
        max_DFT_amplitude_difference=audit['max_DFT_amplitude_difference'],
        max_source_phase_audit_difference_cycles=audit['source_map_difference_cycles'],
        maximum_HF_source_remainder_full_ratio=review['maximum_HF_source_remainder_full_ratio'],
        minimum_HF_source_signed_cross_full_ratio=review['minimum_HF_source_signed_cross_full_ratio'],
        literal_negative_cross_matrices_and_eigenvalues_preserved=True,
        known_deterministic_AM_in_remainder=True, finite_white_noise_projection_nonzero=True,
        new_remainder_detail_target_qualified=False, source_physical_separation=False,
        rejected_interpretation_not_rescued_by_clock_window_order_strength=True,
        failures=['audit1 analytic rising phase bitwise-equality assertion: arithmetic-order rounding; audit2 8ULP metadata assertion only, original gates unchanged; audit3 independently reconstructs fixtures'],
        images_viewed=2, new_C_or_model_or_audio_candidate=False,
        default_driver_owned_take_room_changed=False, unchanged_68CTest_not_repeated=True,
        F2_F3_hearings='independently pending, no repeated questions or blind strength migration',
        E_feedback='左右关系有改善，音色仍明显电子',
        downloaded=False, pushed=False, physical_7_1_4=False, full_goal='active',
        next='Known-first native-frequency harmonic neighborhoods/interline/unresolved-region budgets and envelopes; no direct waveform-subtraction noise target or source-clock rescue. Preserve same driver/stems and separate spatial renderer.')
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(voices)+[n for n in m['protected_before'] if n not in c_files]
    sources += list(m['sources'])+[
        'tools/native_projection_v1/README.md', 'tools/audit_F3_native_projection_v1.py',
        'tools/review_F3_native_projection_v1.py', 'tools/package_F3_native_projection_v1.py',
        'research/F3原生投影与细节交叉项V1.md', 'README.md', 'AGENTS.md',
        'handoff/C文件索引.csv', 'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/F3_native_projection_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', [
        'F3_native_projection_v1', 'baselines/F3_native_projection_v1/manifest.json',
        result['file_count'], result['manifest_sha256'],
        '11known+60real;71stereo477windows68688DFT;independentCholesky-Welch-CSD-cross;2figures',
        '667C-H82voices/F2 exact;remainder not qualified:AM/noise bias/strong signed cancellation;no runtime/audio/hearing migration;audit1roundingfail kept',
        'research/F3原生投影与细节交叉项V1.md | research/F3_native_projection_v1_summary.json',
        'baselines/F3_native_projection_v1/validation.json'])
    print(result)


if __name__ == '__main__':
    main()
