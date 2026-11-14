"""Freeze audited native-time budgets; runtime and voices must remain exact."""
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
    e = a.workspace/'references/analysis/F3_local_detail_budget_v1'
    root = a.workspace/'baselines/F3_local_detail_budget_v1'
    if a.verify:
        result = verify(root)
        print(dict(result='archive_verified', files=result['file_count'], bytes=result['bytes']))
        return
    m, audit, review = [load(e/name/'report.json') for name in ['measure1', 'audit2', 'review1']]
    assert m['result'] == 'six_native_time_stereo_budgets_measured' and len(m['cases']) == 6
    assert audit['result'] == 'independent_native_stereo_budget_audit_passed'
    assert review['result'] == 'six_native_stereo_budget_plots_ready'
    assert audit['producer_report_sha256'] == review['measure_report_sha256'] == sha(e/'measure1/report.json')
    assert review['audit_report_sha256'] == sha(e/'audit2/report.json')
    assert audit['checked_inputs'] == 70 and audit['checked_windows'] == 460
    assert audit['direct_DFT_complex_values'] == 22080
    for folder in ['measure1', 'audit1', 'audit2']:
        r = load(e/folder/'report.json')
        for name, h in r['sources'].items():
            assert sha(e/folder/'exact_sources'/name) == h
            if folder != 'audit1':
                assert sha(repo/name) == h
    assert sha(repo/'tools/review_F3_local_detail_budget_v1.py') == sha(e/'review1/executed_review.py')
    for name, h in m['inputs'].items():
        path = Path(name)
        assert sha(path if path.is_absolute() else repo/path) == h
    for name, h in m['protected_before'].items():
        assert sha(repo/name) == h
    prior = a.workspace/'baselines/catalog_local_F3_v1/evidence'
    c_files, voices = [load(prior/name) for name in ['C_files_sha256.json', 'voice_files_sha256.json']]
    assert len(c_files) == 667 and len(voices) == 82
    index = list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='')))
    assert len(index) == 668 and all(row[4] == c_files[row[0]] for row in index[1:])
    names = set()
    for flags in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']]:
        names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(c_files)
    visual = load(e/'review1/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed']
    for name, h in review['images'].items():
        assert sha(e/'review1'/name) == h
    inputs = {'data_AGENTS.md': a.workspace/'AGENTS.md'}
    for row in m['cases']:
        folder = e/'measure1'/row['label']
        assert sha(folder/'measurement.npz') == row['data_sha256']
        assert len(row['generated']) == 3 and len(row['comparisons']) == len(row['chunks']) == 9
        for item in row['generated']:
            assert sha(folder/('DNA_%d.wav' % item['seed'])) == item['sha256']
        original = Path(row['original_folder'])
        for name in ['result.json', 'selection.json', 'coordinates.npz', 'native.wav', 'reference.wav', 'voice.model']:
            inputs[row['label']+'/'+name] = original/name
    for parent in ['bandlimited_dna_v1', 'F3_pitch_anchors_v1', 'F3_fifth_voice_v1', 'catalog_local_F3_v1']:
        inputs[parent+'_manifest.json'] = a.workspace/'baselines'/parent/'manifest.json'
    shutil.copy2(__file__, e/'executed_package.py')
    validation = dict(
        result='six_frozen_local_anchors_native_time_stereo_budget_complete',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        previous_goal_turn='ADI V5 estimate/artifacts completed; no synthesis changes in that turn.',
        runtime_C_H_exact=667, voice_parameters_exact=82, protected_F2_exact=True,
        new_C_or_runtime_parameters=False, unchanged_CTest_not_repeated=True,
        anchors=6, C_exports=18, C_seconds_each=8, seeds=[1, 23117, 61927],
        equal_duration_C_chunks=54, all_audio_inputs_plus_known=70,
        windows=460, explicit_DFT_complex_values=22080,
        max_matrix_error_FS2=audit['max_matrix_error_FS2'],
        max_direct_DFT_amplitude_error=audit['max_direct_DFT_amplitude_error'],
        max_eigenvalue_error_FS2=audit['max_debt_eigenvalue_error_FS2'],
        HF_total_C_native_band_extrema_dB=review['HF_3_to_14k_C_minus_native_band_extrema_dB'],
        processed_native_max_band_abs_dB=review['processed_native_max_band_abs_dB'],
        mean_PD_all_six_by_band=review['mean_debt_PD_all_six_by_band'],
        raw_hermitian_debt_and_negative_eigenvalues_preserved=True,
        single_chunk_positive_debt_not_universal=True,
        new_audio_candidate=False, hearing=False, physical_source_separation=False,
        native_dynamic_or_real_RPM_load_law=False, physical_7_1_4=False,
        default_driver_take_room_changed=False, downloaded=False, pushed=False,
        F2_F3_hearings='independently pending; no repeated questions or blind strength migration',
        E_feedback='左右关系有改善，音色仍明显电子',
        next='Known-controlled native harmonic/interharmonic power and envelope extraction, then source-supported joint-channel/detail energy budget through existing single driver. No automatic brightness/widening/noise addition.',
        full_goal='active')
    sources = [n for n in names if Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt')]
    sources += list(voices)+[n for n in m['protected_before'] if n not in c_files]
    sources += ['voices/F3_fifth_local_v1/index.json',
                'tools/local_detail_budget_v1/spectrum.py', 'tools/local_detail_budget_v1/README.md',
                'tools/measure_F3_local_detail_budget_v1.py', 'tools/audit_F3_local_detail_budget_v1.py',
                'tools/review_F3_local_detail_budget_v1.py', 'tools/package_F3_local_detail_budget_v1.py',
                'tools/research_archive_v1.py', 'research/F3_local_detail_budget_v1_plan.json',
                'research/F3原生双声道细节预算V1.md', 'README.md', 'AGENTS.md',
                'handoff/C文件索引.csv', 'handoff/开发留痕.md', 'handoff/研究续接.md',
                'handoff/当前代码阅读入口.md']
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/F3_local_detail_budget_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv', [
        'F3_local_detail_budget_v1', 'baselines/F3_local_detail_budget_v1/manifest.json',
        result['file_count'], result['manifest_sha256'],
        '6native anchors;18frozenC;54equalchunks;70inputs460windows22080DFT;allbandWelchCSD-MS-eigen audit;2figures',
        '667C-H82voices/F2 exact;HF2.15-5.29dB short;stereo not simply narrow;literal indefinite debt;no audio/default/hearing changes',
        'research/F3原生双声道细节预算V1.md | research/F3_local_detail_budget_v1_summary.json',
        'baselines/F3_local_detail_budget_v1/validation.json'])
    print(result)


if __name__ == '__main__':
    main()
