"""Freeze fixed five-anchor source evidence, review, and the retained legacy failure."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--verify', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
e = a.workspace/'references/analysis/F3_pitch_anchors_v1'
root = a.workspace/'baselines/F3_pitch_anchors_v1'
if a.verify:
    manifest = verify(root)
    print(dict(result='archive_verified', files=manifest['file_count'], bytes=manifest['bytes']))
    raise SystemExit

prior = a.workspace/'baselines/bandlimited_dna_v1'
protected = prior/'inputs'
old = load(protected/'C_files_sha256.json')
voices = load(protected/'voice_files_sha256.json')
assert len(old) == 656 and len(voices) == 76
assert all(sha(repo/n) == h for n, h in {**old, **voices}.items())
names = set()
for flags in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
    names.update(subprocess.check_output(['git']+flags, cwd=repo).decode('utf-8').split('\0'))
names.discard('')
assert {n for n in names if Path(n).suffix in ('.c', '.h')} == set(old)
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
assert all(sha(repo/n) == sha(prior/'source'/n) for n in f2)

fit = load(e/'fit1/report.json')
audit = load(e/'audit1/report.json')
legacy_bad = load(e/'legacy1/report.json')
legacy = load(e/'legacy2/report.json')
compare = load(e/'compare1/report.json')
review = load(e/'review1/report.json')
browser = load(e/'browser1/report.json')
assert fit['qualified'] == 5 and fit['excluded'] == 0
assert audit['result'] == 'fixed_F3_pitch_anchors_audited' and audit['native_frames'] == 725
assert audit['C_H_exact'] == 656 and audit['voice_parameters_exact'] == 76
assert audit['all_serialized_replays_exact'] and not audit['new_independent_rho_gate_claim']
assert legacy_bad['result'] == 'failed'
assert legacy['result'] == 'legacy_extraction_profile_and_three_C_WAVs_exact'
assert legacy['no_new_extraction'] and all(legacy['source_PCM_exact'].values())
assert legacy['coordinates_array_exact']
assert all(v['only_PEAK_timestamp'] for v in legacy['WAV_container_differences'].values())
assert all(legacy['exact'][n] for n in ('voice.model', 'coordinates.npz', 'DNA_1.wav', 'DNA_23117.wav', 'DNA_61927.wav'))
assert compare['result'] == 'five_F3_common_pitch_descriptive_comparisons_complete'
assert not compare['legacy_root_boundary_exceeded'] and not compare['realism_gate']
assert review['result'] == 'five_F3_native_and_common_root_review_ready' and len(review['clips']) == 45
assert browser['result'] == 'passed' and browser['clips'] == 45 and browser['stale_fetch_prevented']
assert sha(repo/'tools/check_F3_pitch_anchors_v1.cjs') == sha(e/'browser1/executed_check.cjs')

sources = set(old) | set(voices) | set(f2)
sources.update(n for n in names if Path(n).suffix in ('.cmake', '.in') or n.endswith('CMakeLists.txt'))
for phase in ('fit1', 'audit1', 'legacy2', 'compare1', 'review1'):
    report = load(e/phase/'report.json')
    for n, h in report['sources'].items():
        assert sha(repo/n) == h == sha(e/phase/'exact_sources'/n), (phase, n)
        sources.add(n)
    for n, h in report.get('inputs', {}).items():
        assert sha(Path(n)) == h, (phase, n)
# Legacy1's original verification source differs from the corrected reader;
# preserve it as executed, without falsely claiming it matches current code.
for n, h in legacy_bad['sources'].items():
    assert sha(e/'legacy1/exact_sources'/n) == h

sources.update([
    'tools/package_F3_pitch_anchors_v1.py', 'tools/check_F3_pitch_anchors_v1.cjs',
    'tools/build_bandlimited_dna_v1.py', 'tools/research_archive_v1.py',
    'research/F3多音高局部声纹V1.md', 'research/F3_pitch_anchors_v1_plan.json',
    'research/F3_pitch_compare_v1_plan.json', 'research/F3_display_rpm_v1_annotations.json',
    'references/segments_v1.json', 'README.md', 'AGENTS.md',
    'handoff/研究续接.md', 'handoff/开发留痕.md', 'handoff/C文件索引.csv',
    'handoff/C模块与接口.md', 'handoff/当前代码阅读入口.md'])

validation = dict(
    result='five_fixed_local_source_models_and_review_frozen',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='No synthesis progress: ADI cycle recheck reproduced unchanged inputs and estimates; resume unfinished fixed F3 source study.',
    source_cases=[dict(name=v['case']['name'], seconds=v['case']['seconds'],
                       root_hz=v['extraction']['root_hz'], observations=v['observations'],
                       heldout=v['extraction']['heldout_coherence']) for v in fit['cases']],
    source_gates_unchanged=True, source_qualified=5, source_excluded=0,
    root_ratio=compare['acoustic_root_ratio'], legacy_training_root_boundary_exceeded=False,
    independent_native_windows=725, independent_inverse_FLOAT_exact=True,
    all_model_means_and_marginal_covariances_audited=True,
    all_serialized_model_replays_exact=True, independent_SVD_proof=False,
    earlier_absolute_rho_failure_reclassified=False, new_independent_rho_gate=False,
    direct_audit=audit, source_spectrum_comparison=compare,
    C_audio_files=30, seconds_per_generated_file=8, sparse_C_points_per_file=14,
    listening_files=45, common_listening_gain=.5, fade_frames=240,
    browser=browser, screenshots_viewed=3, comparison_plot_viewed=True, human_hearing=False,
    retained_failure='legacy1 demanded complete Python WAV identity; legacy2 proves source PCM exact and only RIFF PEAK timestamp changed, without refit',
    legacy_profile_coordinates_and_three_C_WAVs_exact=True,
    C_H_exact=656, voice_parameters_exact=76, F2_exact=True,
    C_or_live_default_or_driver_or_take_changes=False, new_timbre_accepted=False,
    actual_high_root_recording_validated=False, independent_recordings=False,
    physical_RPM_load=False, physical_7_1_4=False, optimized_ADI_port=False,
    F2_F3_hearings='independently pending; no repeated question, blind strengths or migration',
    E_feedback='左右关系有改善，音色仍明显电子',
    unchanged_70CTest_not_repeated=True, new_download=False, pushed=False, full_goal='active',
    next='Two separate same-context fifth-gear early/mid/late acoustic-root banks, reusing frozen mids and the existing SaVoice/controller; keep sixth separate. Broader states/other engines/high-root-owned-live/physical7.1.4 remain incomplete.')

binary = e/'bin'
binary.mkdir(exist_ok=False)
probe = repo/'build-bandlimited-dna-v1/bin/Release/sound_dna_bandlimited_export.exe'
assert fit['inputs'][str(probe)] == sha(probe)
shutil.copy2(probe, binary/'sound_dna_bandlimited_export.exe')
raw = prior/'evidence/bin/frozen_old_raw_export.exe'
assert sha(raw) == legacy['raw_exporter_sha256']
shutil.copy2(raw, binary/'frozen_old_raw_export.exe')
shutil.copy2(__file__, e/'executed_package.py')
inputs = dict(C_files_sha256=protected/'C_files_sha256.json',
              voice_files_sha256=protected/'voice_files_sha256.json',
              prior_bandlimited_manifest=prior/'manifest.json',
              prior_fifth_manifest=a.workspace/'baselines/F3_fifth_voice_v1/manifest.json',
              approval_manifest=a.workspace/'references/approval_manifest.json',
              data_AGENTS=a.workspace/'AGENTS.md')
frozen_case = a.workspace/'baselines/F3_fifth_voice_v1/evidence/fit1/F3 Fifth First Mid'
for n in ('native.wav', 'normalized.wav', 'reference.wav', 'coordinates.npz', 'voice.model',
          'DNA_1.wav', 'DNA_23117.wav', 'DNA_61927.wav', 'result.json'):
    inputs['legacy_frozen/'+n] = frozen_case/n
result = freeze(root, repo, sources, e, inputs, validation)
verify(root)
save(repo/'research/F3_pitch_anchors_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', [
    'F3_pitch_anchors_v1', 'baselines/F3_pitch_anchors_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '5fixed DNA;725native windows;direct mean/marginal covariance;30x14C sparse;45clip one-player;legacy replay exact',
    '58.23..67.96Hz local only;all roots below legacy boundary;656C-H76voices/F2 exact;no live/hearing promotion',
    'research/F3多音高局部声纹V1.md | research/F3_pitch_anchors_v1_summary.json',
    'baselines/F3_pitch_anchors_v1/validation.json'])
print(result)
