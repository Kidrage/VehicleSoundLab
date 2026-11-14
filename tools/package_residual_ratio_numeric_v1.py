"""Freeze exact moments, original failed-gate status and the synthetic loader boundary."""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--verify', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
evidence = a.workspace/'references/analysis/residual_ratio_numeric_v1'
root = a.workspace/'baselines/residual_ratio_numeric_v1'
if a.verify:
    result = verify(root)
    print(dict(result='archive_verified', files=result['file_count'], bytes=result['bytes']))
    raise SystemExit
controls = load(evidence/'controls1/report.json')
replay = load(evidence/'replay1/report.json')
audit = load(evidence/'audit1/report.json')
failed_limit = load(evidence/'limits1/report.json')
limits = load(evidence/'limits2/report.json')
assert controls['result'] == 'known_exact_moment_and_perturbation_controls_passed'
assert replay['result'] == 'frozen_models_replay_exact_and_literal_rho_moments_verified'
assert audit['result'] == 'independent_fraction_moments_and_conditional_bounds_verified'
assert limits['result'] == 'existing_288harmonic_profile_limit_reproduced'
assert failed_limit['result'] == 'failed' and failed_limit['error'] == 'AssertionError()'
assert sha(evidence/'limits1/known_0.wav') == sha(evidence/'limits2/known_0.wav')
assert [v['exit_code'] for v in limits['cases']] == [0, 2, 2]
assert not replay['original_projection_gate_passed'] and not replay['original_audit_relabelled']
assert not audit['all_original_parameter_audits_passed']
sources = set()
for attempt in ('controls1', 'replay1', 'audit1', 'limits2'):
    report = load(evidence/attempt/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == digest == sha(evidence/attempt/'exact_sources'/name)
        sources.add(name)
    for name, digest in report.get('inputs', {}).items():
        assert sha(name) == digest
parent = a.workspace/'baselines/F3_fifth_voice_v1'
verify(parent)
protected = a.workspace/'baselines/catalog_F3_v1/inputs'
cfiles = load(protected/'C_files_sha256.json')
voices = load(protected/'voice_files_sha256.json')
assert len(cfiles) == 650 and len(voices) == 76
assert all(sha(repo/name) == digest for name, digest in {**cfiles, **voices}.items())
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
for name in f2:
    assert sha(repo/name) == sha(a.workspace/'baselines/catalog_F3_v1/source'/name)
sources.update(f2)
sources.update(['tools/package_residual_ratio_numeric_v1.py', 'AGENTS.md',
                'research/微弱残差数值核查V1.md', 'research/F3五挡局部声线V1.md',
                'handoff/研究续接.md', 'handoff/开发留痕.md', 'handoff/C模块与接口.md'])
validation = dict(
    result='literal_rho_calculation_verified_original_alternative_gate_retained',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='Progress: two fixed local F3 voices/source gates and12C comparisons frozen with unresolved extra quotient audit.',
    known_cases=8, primitive_cases=4, known_harmonic_checks=64, source_harmonic_checks=576,
    tamper_rejections=640, source_conditional_pairs=1728,
    model_replay_exact=[dict(name=v['name'], sha256=v['original_model_sha256'],
                            maximum_literal_error=v['exact_moment_maximum_error']) for v in replay['cases']],
    independent_fraction_audit=audit, independent_SVD=False,
    original_alternative_1e9_gate_passed=False, original_audit_relabelled=False,
    conditional_bounds_are_not_universal_forward_error=True,
    images_viewed=1, new_timbre_audio=False, synthetic_boundary_waveforms=1,
    synthetic_wave_frames=480, duplicate_synthetic_wave_preserved_across_attempts=True,
    profile_loading_limit=limits, actual_high_source_root_measured=False,
    all_attempts=['controls1', 'replay1', 'audit1', 'limits1', 'limits2'],
    failure_preserved='limits1 assumed format tag3 instead of existing WAVEFORMATEXTENSIBLE FLOAT GUID; limits2 only corrects RIFF decoding.',
    C_H_exact=650, voice_files_exact=76, F2_exact=True,
    runtime_UI_driver_default_takes_unchanged=True, new_live_profiles=False,
    original_67CTest_not_repeated=True, downloaded=False, pushed=False,
    F2_F3_hearings='Independently pending; no repeated request, blind strengths or default migration',
    E_feedback='左右关系有改善，音色仍明显电子', full_goal='active',
    next='Explicit opt-in bandlimited profile/render/atlas interfaces, reusing texture and one controller; preserve old guard/bytes/takes. Known alias/taper/block controls before any higher-root source anchors. Stop tiny-ratio/source-window rescue.')
inputs = {
    'C_files_sha256.json': protected/'C_files_sha256.json',
    'voice_files_sha256.json': protected/'voice_files_sha256.json',
    'parent_manifest.json': parent/'manifest.json',
    'data_AGENTS.md': a.workspace/'AGENTS.md',
    'original_fit_report.json': parent/'evidence/fit1/report.json',
    'original_failed_projection_audit.json': parent/'evidence/audit2/report.json',
    'original_plan.json': parent/'evidence/fit1/exact_sources/research/F3_fifth_voice_v1_plan.json'}
for i, case in enumerate(replay['cases']):
    folder = parent/'evidence/fit1'/case['name']
    for name in ('native.wav', 'voice.model', 'coordinates.npz'):
        inputs[f'case{i}_{name}'] = folder/name
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo/'research/residual_ratio_numeric_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', [
    'residual_ratio_numeric_v1', 'baselines/residual_ratio_numeric_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '8known+4primitives;640literal rho/tamper;1728conditional pairs;independent Fraction;oldC synthetic guard',
    'Original1e-9failure retained;2models byte-exact;650C-H76voices/F2 exact;no live/hearing promotion;288H root guard68.18Hz',
    'research/微弱残差数值核查V1.md | research/residual_ratio_numeric_v1_summary.json',
    'baselines/residual_ratio_numeric_v1/validation.json'])
print(result)
