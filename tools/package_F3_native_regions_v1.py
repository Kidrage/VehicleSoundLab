"""Freeze disjoint native regions, failed audits and full stereo observations."""
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
    e = a.workspace/'references/analysis/F3_native_regions_v1'
    root = a.workspace/'baselines/F3_native_regions_v1'
    if a.verify:
        result = verify(root)
        print(dict(result='archive_verified', files=result['file_count'], bytes=result['bytes']))
        return
    m, audit, review = [load(e/n/'report.json') for n in ['measure1', 'audit3', 'review1']]
    assert m['result'] == 'native_frequency_regions_measured'
    assert audit['result'] == 'independent_native_regions_audit_passed'
    assert review['result'] == 'native_regions_and_full_envelopes_published'
    assert audit['producer_report_sha256'] == review['producer_report_sha256'] == sha(e/'measure1/report.json')
    assert review['audit_report_sha256'] == sha(e/'audit3/report.json')
    assert len(m['known']) == 13 and len(m['cases']) == 6
    assert m['source_stereo_inputs'] == 6 and m['C_stereo_inputs'] == 54
    assert (audit['stereo_inputs'], audit['windows'], audit['DFT_complex_values']) == (73, 718, 34464)
    for n, h in m['sources'].items():
        assert sha(e/'measure1/exact_sources'/n) == sha(repo/n) == h
    for n, h in m['inputs'].items():
        assert sha(n) == h
    for n, h in m['protected_before'].items():
        assert sha(repo/n) == h
    failed1, failed2 = [load(e/n/'report.json') for n in ['audit1', 'audit2']]
    assert failed1['result'] == failed2['result'] == 'failed'
    assert len(failed1['cases']) == 5 and len(failed2['cases']) == 9
    assert 'literal PSD eigenvalues' in failed1['error']
    assert failed2['error'] == 'AssertionError()'
    assert all((e/n/'executed_audit.py').is_file() for n in ['audit1', 'audit2'])
    assert sha(repo/'tools/audit_F3_native_regions_v1.py') == sha(e/'audit3/executed_audit.py') == audit['auditor_sha256']
    assert sha(repo/'tools/review_F3_native_regions_v1.py') == sha(e/'review1/executed_review.py')
    assert load(e/'review1/visual_review.json')['two_scientific_figures_individually_viewed']
    for n, h in review['images'].items():
        assert sha(e/'review1'/n) == h
    assert sha(e/'review1/full_band_observations.json') == review['full_observations_sha256']
    assert review['no_clean_interline_bins_at_or_above_6k']
    for row in m['known']+[c[k] for c in m['cases'] for k in ['source', 'C']]:
        assert sha(e/'measure1'/row['label']/'arrays.npz') == row['data_sha256']
    prior = a.workspace/'baselines/catalog_local_F3_v1/evidence'
    c_files, voices = [load(prior/n) for n in ['C_files_sha256.json', 'voice_files_sha256.json']]
    assert len(c_files) == 667 and len(voices) == 82
    for n, h in dict(c_files, **voices).items():
        assert sha(repo/n) == h
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
        result='native_regions_verified_no_clean_HF_interline_target',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        previous_goal_turn='No synthesis progress: ADI estimate rechecked, same bound and no DSP change. Current turn completes native-region evidence and chooses longer full-band stereo observation.',
        runtime_C_H_exact=667, voice_parameters_exact=82, F2_exact=True,
        known_cases=13, source_stereo_inputs=6, C_stereo_inputs=54,
        all_stereo_inputs=73, all_windows=718, explicit_DFT_complex_values=34464,
        max_matrix_difference_FS2=audit['max_matrix_error_FS2'],
        max_DFT_amplitude_difference=audit['max_DFT_error'],
        max_root_bound_difference_Hz=audit['max_root_bound_error_Hz'],
        overlap_6_to14k_fraction_extrema=review['source_6_to14k_overlap_fraction_extrema'],
        no_clean_interline_bins_at_or_above_6k=True, physical_noise_absent=False,
        physical_source_separation=False, independent_noise_target_qualified=False,
        full_stereo_observations_preserved=True, observation_is_runtime_preset=False,
        failures=['audit1 eigenvalue input perturbation', 'audit2 real covariance cannot verify imaginary one-sided cross; audit3 independent Hilbert check'],
        failures_and_executed_sources_preserved=True, original_matrix_gates_unchanged=True,
        images_viewed=2, new_C_or_model_or_audio_candidate=False,
        default_driver_owned_take_room_changed=False, unchanged_68CTest_not_repeated=True,
        F2_F3_hearings='independently pending, no repeated questions or blind strength migration',
        E_feedback='左右关系有改善，音色仍明显电子',
        downloaded=False, pushed=False, physical_7_1_4=False, full_goal='active',
        next='Known-first longer approved original-time F3 fifth segments: joint full-band envelopes and LR association. Do not rescue clock/window/order to manufacture independent noise.')
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(voices)+[n for n in m['protected_before'] if n not in c_files]
    sources += list(m['sources'])+[
        'tools/native_regions_v1/README.md', 'tools/audit_F3_native_regions_v1.py',
        'tools/review_F3_native_regions_v1.py', 'tools/package_F3_native_regions_v1.py',
        'research/F3原生频谱区域与包络V1.md', 'README.md', 'AGENTS.md',
        'handoff/C文件索引.csv', 'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/当前代码阅读入口.md']
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/F3_native_regions_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', [
        'F3_native_regions_v1', 'baselines/F3_native_regions_v1/manifest.json',
        result['file_count'], result['manifest_sha256'],
        '13known+60real;73stereo718windows34464DFT;independent regions-Welch-CSD-Hilbert;2figures',
        '667C-H82voices/F2 exact;6k+no clean gaps under declared mask;not absence of noise;audit1/2 failures kept;no runtime or hearing migration',
        'research/F3原生频谱区域与包络V1.md | research/F3_native_regions_v1_summary.json',
        'baselines/F3_native_regions_v1/validation.json'])
    print(result)


if __name__ == '__main__':
    main()
