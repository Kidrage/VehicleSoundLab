"""Freeze both capture protocols and independently verified joint budgets."""
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
    e = a.workspace / 'references/analysis/F3_driver_joint_v1'
    root = a.workspace / 'baselines/F3_driver_joint_v1'
    if a.verify:
        report = verify(root)
        print(dict(result='archive_verified', files=report['file_count'], bytes=report['bytes']))
        return
    prior = a.workspace / 'baselines/catalog_local_F3_v1/evidence'
    original_c, voices = [load(prior / n) for n in ['C_files_sha256.json', 'voice_files_sha256.json']]
    assert len(original_c) == 667 and len(voices) == 82
    names = set()
    for flags in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']]:
        names.update(subprocess.check_output(['git'] + flags, cwd=repo).decode('utf8').split('\0'))
    names.discard('')
    current_c = {n: sha(repo / n) for n in names if Path(n).suffix in ('.c', '.h')}
    new_c = {'experiments/joint_capture_v1/' + n for n in ['session.c', 'session.h', 'probe.c']}
    assert len(current_c) == 670 and set(current_c)-set(original_c) == new_c
    assert all(current_c[n] == h for n, h in original_c.items())
    assert all(sha(repo / n) == h for n, h in voices.items())
    parent_joint = a.workspace / 'baselines/F3_joint_envelopes_v1'
    assert sha(parent_joint/'manifest.json') == load(repo/'research/F3_joint_envelopes_v1_summary.json')['manifest_sha256']
    parent_catalog = a.workspace/'baselines/catalog_local_F3_v1'
    assert sha(parent_catalog/'manifest.json') == load(repo/'research/catalog_local_F3_v1_summary.json')['manifest_sha256']
    catalog_files = {row['path']: row['sha256'] for row in load(parent_catalog/'manifest.json')['files']}
    protected_f2 = {n: catalog_files['source/'+n] for n in [
        'experiments/modal_idle_v1/F2_fixed_idle.msource',
        'experiments/modal_texture_v1/F2_amplitude.mtexture',
        'experiments/spectral_texture_v1/F2_fine_static.sfir']}
    assert all(sha(repo/n) == h for n, h in protected_f2.items())
    assert all(sha(parent_catalog/'source'/n) == h for n, h in protected_f2.items())
    index = list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='')))
    assert len(index) == 671 and {row[0] for row in index[1:]} == set(current_c)
    assert all(row[4] == current_c[row[0]] for row in index[1:])
    save(e/'C_files_sha256.json', current_c)
    save(e/'voice_files_sha256.json', voices)
    save(e/'F2_files_sha256.json', protected_f2)
    reports = {}
    render_id = '7d790f43bb7653eabd62d6217d15dc33b3df83dc5ebd3eda836080ce3326d4cf'
    for version in [1, 2]:
        build_path = e/f'build{version}'
        build = load(build_path/'report.json')
        assert build['result'] == 'joint_capture_built'
        assert sha(build_path/'joint_capture.exe') == build['binary_sha256']
        assert all(c['exit_code'] == 0 and sha(build_path/c['log']) == c['sha256'] for c in build['commands'])
        for name, h in build['sources'].items():
            assert sha(build_path/'exact_sources'/name) == h
            if name in original_c:
                assert h == original_c[name]
            if version == 2:
                assert sha(repo/name) == h
        for group, result, count in [('known', 'known_one_driver_capture_passed', 2),
                                      ('capture', 'three_separate_F3_driver_recipes_captured', 9)]:
            folder = e/f'{group}{version}'
            capture = load(folder/'report.json')
            assert capture['result'] == result and len(capture['cases']) == count
            assert capture['binary_sha256'] == build['binary_sha256']
            if group == 'known':
                assert capture['historical_owned_take_and_WAV_exact']
            if version == 2:
                assert capture['previous_capture_exact']
            for name, h in capture['sources'].items():
                assert sha(folder/'exact_sources'/name) == h
                if version == 2:
                    assert sha(repo/name) == h
            for command in capture['commands']:
                assert sha(folder/command['log']) == command['sha256']
                assert command['exit_code'] in [0, 2, 3, 4]
            assert not list((folder/'no_external_voices').iterdir())
            for row in capture['cases']:
                case = folder/row['label']
                assert sha(case/'drive.vslrun') == row['take_sha256']
                for output in row['outputs']:
                    assert output['report']['verified']
                    assert output['report']['render_id'] == render_id
                    for name, h in output['files'].items():
                        assert sha(case/name) == h
                    if version == 2:
                        old = e/f'{group}1'/row['label']
                        for suffix in ['_out.wav', '_layers.wav', '.csv']:
                            name = output['tag'] + suffix
                            assert sha(case/name) == sha(old/name)
                        assert sha(case/'drive.vslrun') == sha(old/'drive.vslrun')
            measure_name = ('known_measure' if group == 'known' else 'measure') + str(version)
            audit_name = ('known_audit' if group == 'known' else 'audit') + str(version)
            measure = load(e/measure_name/'report.json')
            audit = load(e/audit_name/'report.json')
            assert measure['result'] == 'existing_one_driver_joint_budgets_measured'
            assert audit['result'] == 'independent_driver_joint_audit_passed'
            assert len(measure['cases']) == len(audit['cases']) == count
            assert audit['producer_report_sha256'] == sha(e/measure_name/'report.json')
            assert audit['auditor_sha256'] == sha(e/audit_name/'executed_audit.py')
            assert audit['windows'] == 137*count
            assert audit['DFT_complex_values'] == 137*count*24*2*(5 if version == 2 else 4)
            for name, h in measure['sources'].items():
                assert sha(e/measure_name/'exact_sources'/name) == h
                if version == 2:
                    assert sha(repo/name) == h
            for name, h in measure['inputs'].items():
                assert sha(name) == h
            for row in measure['cases']:
                assert sha(e/measure_name/row['label']/'arrays.npz') == row['arrays_sha256']
                if 'comparison_sha256' in row:
                    assert sha(e/measure_name/row['label']/'source_comparison.npz') == row['comparison_sha256']
            reports[audit_name] = audit
    for name in ['tools/audit_F3_driver_joint_v1.py']:
        assert sha(repo/name) == reports['audit2']['auditor_sha256'] == reports['known_audit2']['auditor_sha256']
    review = load(e/'review1/report.json')
    assert review['result'] == 'one_driver_joint_budget_observations_published'
    assert review['producer_report_sha256'] == sha(e/'measure2/report.json')
    assert review['audit_report_sha256'] == sha(e/'audit2/report.json')
    assert review['observations_sha256'] == sha(e/'review1/observations.json')
    assert sha(repo/'tools/review_F3_driver_joint_v1.py') == sha(e/'review1/executed_review.py')
    for name, h in review['images'].items():
        assert sha(e/'review1'/name) == h
    for name, h in review['inputs'].items():
        assert sha(name) == h
    visual = load(e/'review1/visual_review.json')
    assert visual['two_scientific_figures_individually_viewed']
    assert visual['images_sha256'] == review['images']
    transient = load(e/'transient1/report.json')
    assert transient['result'] == 'four_new_original_PTS_frames_prepared'
    assert sha(transient['video']) == transient['video_sha256']
    assert sha(e/'transient1/context.png') == transient['context_sha256']
    for row in transient['frames']:
        assert sha(e/'transient1'/row['file']) == row['sha256']
    annotations = load(repo/'research/F3_driver_joint_v1_transient_annotations.json')
    assert annotations['board_sha256'] == transient['context_sha256']
    assert all(row[1] == 5 for row in annotations['rows'])
    receipt = load(e/'transient1/visual_review.json')
    assert receipt['four_original_PTS_frames_viewed']
    assert receipt['annotations_sha256'] == sha(repo/'research/F3_driver_joint_v1_transient_annotations.json')
    assert load(e/'package_attempt1/report.json')['result'] == 'failed_before_archive_write'
    assert (e/'package_attempt1/executed_package.py').is_file()
    observed = load(e/'review1/observations.json')
    validation = dict(result='existing_one_driver_joint_budgets_verified',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='No synthesis progress: unchanged ADI inputs and cost model rechecked; resumed current C capture and source evidence.',
        prior_C_H_exact=667,new_offline_C_H=3,total_C_H=670,voice_parameters_exact=82,F2_exact=True,
        real_cases=9,known_cases=2,separate_signed_controls=3,
        real_windows=reports['audit2']['windows'],real_DFT_complex_values=reports['audit2']['DFT_complex_values'],
        known_windows=reports['known_audit2']['windows'],known_DFT_complex_values=reports['known_audit2']['DFT_complex_values'],
        max_matrix_error_FS2=reports['audit2']['max_matrix_error_FS2'],max_DFT_error=reports['audit2']['max_DFT_error'],
        max_statistic_error=reports['audit2']['max_statistic_error'],
        protocol1_and_protocol2_all_attempts_kept=True,original_outputs_layers_CSV_takes_exact=True,
        render_id=render_id,raw_pre_envelope_verified=True,
        packaging_prefix_vs_full_identity_failure_retained=True,
        BENCH_operating='FREE_REV; command gear5 is not physical fifth-gear reconstruction',
        local_observations=observed['local'],separate_preupshift=observed['separate_preupshift'],
        source_peak_and_all_negative_covariance_directions_retained=True,original_PTS_frames_viewed=4,
        scientific_figures_viewed=2,additional_modulation_qualified=False,runtime_preset=False,
        synchronized_source_reconstruction=False,physical_source_separation=False,
        runtime_DSP_model_default_driver_owned_take_room_changed=False,
        unchanged_68CTest_not_repeated=True,F2_F3_hearings='independently pending, no repeat or strength sweep',
        E_feedback='左右关系有改善，音色仍明显电子',downloaded=False,pushed=False,physical_7_1_4=False,
        full_goal='active',next='Known common/differential modulation and changing-root controls to distinguish trajectory effects; jointly reallocate existing DNA variation and missing stereo HF detail, no independent-noise or source-envelope transplant.')
    sources = [n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources += list(voices) + list(protected_f2)
    sources += [n for n in names if n.startswith('tools/driver_joint_v1/') and n.endswith('.py')]
    sources += ['tools/'+n+'_F3_driver_joint_v1.py' for n in ['run','measure','audit','review','package']]
    sources += ['tools/build_joint_capture_v1.py','tools/inspect_F3_joint_transient_v1.py',
        'tools/joint_envelopes_v1/features.py','tools/research_archive_v1.py',
        'research/F3_driver_joint_v1_plan.json','research/F3_driver_joint_v1_transient_plan.json',
        'research/F3_driver_joint_v1_transient_annotations.json','research/F3_display_rpm_v1_annotations.json',
        'research/F3统一驾驶联合细节预算V1.md','experiments/joint_capture_v1/README.md',
        'README.md','AGENTS.md','handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    historical = a.workspace/'baselines/catalog_local_F3_v1/evidence/regress1/new_render/voice_5.vslrun'
    inputs = dict(data_AGENTS=a.workspace/'AGENTS.md',parent_joint_manifest=parent_joint/'manifest.json',
        parent_native_plan=parent_joint/'source/research/F3_joint_envelopes_v1_plan.json',
        parent_source_first_arrays=parent_joint/'evidence/measure1/F3_fifth1/arrays.npz',
        parent_source_second_arrays=parent_joint/'evidence/measure1/F3_fifth2/arrays.npz',
        parent_source_report=parent_joint/'evidence/measure1/report.json',
        parent_catalog_manifest=a.workspace/'baselines/catalog_local_F3_v1/manifest.json',
        historical_owned_take=historical,historical_WAV=historical.with_suffix('.wav'))
    shutil.copy2(__file__, e/'executed_package.py')
    result = freeze(root, repo, sources, e, inputs, validation)
    verify(root)
    save(repo/'research/F3_driver_joint_v1_summary.json', dict(validation, **result))
    append_index(repo/'handoff/阶段索引.csv',[
        'F3_driver_joint_v1','baselines/F3_driver_joint_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        'original driver-owned capture v1-v2;2known+9real;1233windows295920DFT;raw-envelope-six-buses;4PTS+2figures',
        '667oldC-H82voices/F2 exact+3offlineC-H;raw HF common variation;negative covariance retained;FREE_REV engineering trace;no runtime migration',
        'research/F3统一驾驶联合细节预算V1.md | research/F3_driver_joint_v1_summary.json','baselines/F3_driver_joint_v1/validation.json'])
    print(result)


if __name__ == '__main__':
    main()
