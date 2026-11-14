"""Freeze source-derived E timbre candidates and all qualification attempts."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
evidence = a.workspace/'references/analysis/E_decel_source_v1'
baseline = a.workspace/'baselines/catalog_bridge_v1'
root = a.workspace/'baselines/E_decel_source_v1'
old_c = load(baseline/'inputs/C_files_sha256.json')
old_voices = load(baseline/'inputs/voice_files_sha256.json')
assert len(old_c) == 643 and all(sha(repo/n) == h for n, h in old_c.items())
assert len(old_voices) == 72 and all(sha(repo/n) == h for n, h in old_voices.items())
fixtures = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
            'experiments/modal_texture_v1/F2_amplitude.mtexture',
            'experiments/spectral_texture_v1/F2_fine_static.sfir']
for name in fixtures:
    assert sha(repo/name) == sha(baseline/'source'/name)
failed = load(evidence/'fit1/report.json')
assert failed['result'] == 'failed' and failed['error'] == 'AssertionError()'
fit = load(evidence/'fit2/report.json')
assert fit['result'] == 'fixed_centers_checked' and fit['accepted_count'] == fit['rejected_count'] == 1
stereo = load(evidence/'stereo1/report.json')
assert stereo['result'] == 'stereo_extension_rendered' and stereo['same_main'] and not stereo['skipped']
assert len(stereo['models']) == 8 and len(stereo['trials']) == 3 and stereo['main_first8s_exact']
audit = load(evidence/'audit2/report.json')
assert audit['result'] == 'passed' and len(audit['stereo_certificate_checks']) == 8 and len(audit['stereo_trials']) == 3
for stage in ['fit1', 'fit2', 'stereo1', 'audit1', 'audit2']:
    report = load(evidence/stage/'report.json')
    for name, digest in report['sources'].items():
        assert sha(evidence/stage/'exact_sources'/name) == digest
        if stage in ['fit2', 'stereo1', 'audit2']:
            assert sha(repo/name) == digest
review = load(evidence/'review2/report.json')
browser = load(evidence/'browser2/report.json')
assert review['result'] == browser['result'] == 'passed'
assert review['clip_count'] == browser['combinations'] == 17
assert sha(repo/'tools/review_E_decel_source_v1.py') == sha(evidence/'review2/executed_review.py')
assert sha(repo/'tools/decel_source_v1/review.html') == sha(evidence/'review2/executed_review.html')
assert sha(repo/'tools/check_E_decel_source_v1.cjs') == sha(evidence/'browser2/executed_check.cjs')
for name in ['audit2/carriers.png', 'review2/spectrum.png', 'browser2/desktop.png', 'browser2/mobile.png']:
    assert (evidence/name).is_file()
binary = evidence/'bin'
binary.mkdir()
for name in ['VslSoundDna_probe.exe', 'VslResonantDetail_probe.exe', 'VslStereoResonance_probe.exe']:
    path = repo/'build-catalog-bridge-v1/bin/Release'/name
    assert any(str(path) in report['inputs'] and report['inputs'][str(path)] == sha(path) for report in [fit, stereo])
    shutil.copy2(path, binary/name)
# Include the exact original visual evidence actually reviewed this turn.
context = evidence/'visual_context'
context.mkdir()
prior = a.workspace/'baselines/shift_repeat_v1'
manifest = load(prior/'manifest.json')
digests = {row['path']: row['sha256'] for row in manifest['files']}
for name in ['report.json', 'sheet_03.jpg', 'sheet_04.jpg', 'sheet_05.jpg']:
    relative = 'evidence/exploration1/'+name
    assert sha(prior/relative) == digests[relative]
    shutil.copy2(prior/relative, context/name)
save(context/'review.json', dict(reviewed_sheets=['sheet_03.jpg','sheet_04.jpg','sheet_05.jpg'],
    observed='51.5..55s third gear; displayed126 to98km/h;52.25s120km/h;54s105km/h',
    not_established=['exact audio/video alignment','pedals','torque/load','fuel cut','actual RPM']))
sources = list(old_c)+list(old_voices)+fixtures
sources += ['tools/run_E_decel_source_v1.py', 'tools/fit_E_decel_stereo_v1.py',
            'tools/audit_E_decel_source_v1.py', 'tools/review_E_decel_source_v1.py',
            'tools/check_E_decel_source_v1.cjs', 'tools/package_E_decel_source_v1.py',
            'research/E_decel_source_v1_plan.json', 'research/E_decel_stereo_v1_plan.json',
            'research/E_decel_source_v1_listening.json', 'research/E减速声线与双声道细节V1.md',
            'README.md', 'AGENTS.md', 'handoff/算法说明.md', 'handoff/C模块与接口.md',
            'handoff/开发留痕.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv']
sources += sorted({name for report in [fit, stereo, audit] for name in report['sources']})
sources += [path.relative_to(repo).as_posix() for path in (repo/'tools/decel_source_v1').glob('*') if path.is_file()]
sources += ['research/resonant_detail_v1_plan.json','tools/idle_texture_v1/profile.py']
mono_max = max(row['complex_coherence_error'] for trial in fit['accepted'][0]['renders'] for row in trial['metrics'])
validation = dict(result='one_local_E_slowing_voice_and_joint_stereo_detail_candidates',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_exact=643,voice_parameters_exact=72,F2_original_exact=True,new_C_H=0,
    source='approved E first Corsa cabin slowing context', fixed_time_centers=[52.25,54],
    qualified=1,excluded=1,root_hz=fit['accepted'][0]['root_hz'],
    mono_detail_maximum_complex_coherence_difference=mono_max,
    stereo_detail_maximum_complex_coherence_differences=[v['maximum_complex_coherence_error'] for v in stereo['trials']],
    stereo_detail_maximum_power_error_db=[v['maximum_power_error_db'] for v in stereo['trials']],
    joint_detail_C_seconds_per_seed=32,all_three_seeds_retained=True,
    same_main_and_withdrawal=True,known_checks_before_respective_fits=True,
    independent_native_samples_apertures_carriers_PSD_CSD_certificates=True,
    browser_combinations=17,final_browser_muted=True,final_images_reviewed=4,original_video_contact_sheets_reviewed=3,
    previous65CTest_not_rerun='No C/runtime/default change; existing suite remains separate evidence',
    preserved_failure='fit1 entire registry document hash changed; exact E source/sample/context fields are unchanged; fit2 retains both registry identities',
    all_attempts_preserved=['fit1','fit2','audit1','review1','browser1','stereo1','audit2','review2','browser2'],
    listening=load(repo/'research/E_decel_source_v1_listening.json'),
    not_established=['physical/source separation','exact RPM/load/pedal or fuel cut','complete clock qualification',
                     'independent deceleration recording validation','full-state driving timbre','new real engine',
                     'native/device/performance validation for this candidate','physical7.1.4'],
    driver_mapping=False,native_default_changed=False,room_added=False,PCM_timeline=False,
    full_goal='active',next='Judge new candidate hearing and independent source/state support; idle question remains independent. No automatic strength/clock-gate/chaos sweep.')
inputs = {'previous_catalog_manifest.json': baseline/'manifest.json',
          'C_files_sha256.json': baseline/'inputs/C_files_sha256.json',
          'voice_files_sha256.json': baseline/'inputs/voice_files_sha256.json',
          'segments_v1.json': a.workspace/'references/segments_v1.json',
          'approval_manifest.json': a.workspace/'references/approval_manifest.json',
          'prior_shift_repeat_manifest.json': prior/'manifest.json',
          'shift_repeat_annotations.json': repo/'research/shift_repeat_v1_annotations.json',
          'data_AGENTS.md': a.workspace/'AGENTS.md'}
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo/'research/E_decel_source_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['E_decel_source_v1','baselines/E_decel_source_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '1qualified/1excluded fixed source;existing C OSC/Rdt/Rvs;3x32s joint detail;17 browser combinations;independent audit',
    'one cabin context;not physical overrun/load/RPM or full driving/multi-engine/7.1.4/hearing acceptance',
    'research/E减速声线与双声道细节V1.md | research/E_decel_source_v1_summary.json',
    'baselines/E_decel_source_v1/validation.json'])
print(result)
