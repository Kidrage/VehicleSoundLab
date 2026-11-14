"""Freeze both fixed local voices and unresolved audit/known-reference failures."""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--verify', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
evidence = a.workspace/'references/analysis/F3_fifth_voice_v1'
root = a.workspace/'baselines/F3_fifth_voice_v1'
if a.verify:
    result = verify(root)
    print(dict(result='archive_verified', files=result['file_count'], bytes=result['bytes']))
    raise SystemExit

parent = a.workspace/'baselines/catalog_F3_v1'
protected = parent/'inputs'
old = load(protected/'C_files_sha256.json')
voices = load(protected/'voice_files_sha256.json')
assert len(old) == 650 and len(voices) == 76
assert all(sha(repo/name) == digest for name, digest in {**old, **voices}.items())
fit = load(evidence/'fit1/report.json')
first_audit = load(evidence/'audit1/report.json')
audit = load(evidence/'audit2/report.json')
first_compare = load(evidence/'compare1/report.json')
comparison = load(evidence/'compare2/report.json')
verified = load(evidence/'verify1/report.json')
assert fit['qualified'] == 2 and fit['excluded'] == 0
assert first_audit['result'] == first_compare['result'] == 'failed'
assert audit['result'] == 'audit_complete_with_unresolved_residual_rho_ratio'
assert audit['frames_checked'] == 370 and not audit['residual_rho_absolute_gate_passed']
assert comparison['result'] == 'descriptive_comparison_complete' and not comparison['original_audit_ratio_gate_passed']
assert verified['result'] == 'comparison_outputs_verified_ratio_gate_still_unresolved'
assert not first_compare['inputs']  # Known fixture failed before any real-source read.
sources = set(old) | set(voices)
for attempt in ('fit1', 'audit2', 'compare2', 'verify1'):
    report = load(evidence/attempt/'report.json')
    for name, digest in report['sources'].items():
        assert sha(repo/name) == digest == sha(evidence/attempt/'exact_sources'/name)
        sources.add(name)
    for name, digest in report.get('inputs', {}).items():
        assert sha(Path(name)) == digest
f2 = ['experiments/modal_idle_v1/F2_fixed_idle.msource',
      'experiments/modal_texture_v1/F2_amplitude.mtexture',
      'experiments/spectral_texture_v1/F2_fine_static.sfir']
for name in f2:
    assert sha(repo/name) == sha(parent/'source'/name)
sources.update(f2)
sources.update(['tools/package_F3_fifth_voice_v1.py', 'AGENTS.md', 'references/segments_v1.json',
                'research/F3五挡局部声线V1.md', 'research/F3_fifth_compare_v1_plan.json',
                'research/F3_fifth_voice_v1_plan.json', 'research/F3_display_rpm_v1_annotations.json',
                'handoff/研究续接.md', 'handoff/开发留痕.md', 'handoff/C文件索引.csv',
                'handoff/C模块与接口.md'])
validation = dict(
    result='two_local_source_gates_supported_full_parameter_audit_unresolved',
    git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    previous_goal_turn='Progress: current-source ADI V4 inventory/cycle budget reproduced and committed; no DSP or timbre change.',
    plan_predates_MCPS_interruption=True,
    cases=[dict(case=v['case'], root_hz=v['extraction']['root_hz'],
                observations=v['observations'], heldout=v['extraction']['heldout_coherence']) for v in fit['cases']],
    acoustic_source_gates_unchanged=True, source_qualified=2, source_excluded=0,
    parameter_audit_passed=False, residual_rho_absolute_gate=1e-9,
    original_ratio_checks=[v['residual_rho_check'] for v in audit['cases']],
    fixed_numerical_diagnosis=[v['reduced_argument_ratio_check'] for v in comparison['cases']],
    direct_audit=audit, comparison_verification=verified,
    source_model_comparison=comparison['cross_context'],
    C_H_exact=650, voice_files_exact=76, F2_exact=True,
    C_audio_files=12, seconds_per_generated_file=8, sampled_oracle_points_per_file=14,
    reused_original_PTS_annotations=20, images_viewed=2, human_hearing=False,
    all_attempts=['fit1', 'audit1', 'audit2', 'compare1', 'compare2', 'verify1'],
    failures_preserved=['audit1 additional absolute residual-rho ratio assertion failed',
                        'audit2 continues other checks but retains unresolved raw ratio gate',
                        'compare1 infinite analytic-tone cross was not exact finite real Hann-band reference before source read'],
    finite_reference_correction=comparison['known_finite_cross_error'],
    original_ideal_reference_discrepancy=comparison['known_ideal_cross_difference'],
    runtime_UI_driver_default_takes_unchanged=True, live_profiles_promoted=False,
    generic_phase_extractor_qualified=False, physical_RPM_load=False,
    new_listening_acceptance=False, downloaded=False, pushed=False,
    F2_F3_hearings='independently pending; no repeated question, strength sweep, or migration',
    E_feedback='左右关系有改善，音色仍明显电子', old_67CTest_not_repeated=True,
    full_goal='active',
    next='Controlled tiny-residual numerical conditioning before frozen-model verification; independent broader pitch/state evidence, no source/window/gate rescue or near-root wide-RPM claim.')
inputs = dict(C_files_sha256=protected/'C_files_sha256.json',
              voice_files_sha256=protected/'voice_files_sha256.json',
              prior_system_manifest=parent/'manifest.json',
              approval_manifest=a.workspace/'references/approval_manifest.json',
              data_AGENTS=a.workspace/'AGENTS.md',
              raw_C_exporter=Path(next(name for name in fit['inputs'] if name.endswith('sound_dna_export.exe'))))
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo/'research/F3_fifth_voice_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', [
    'F3_fifth_voice_v1', 'baselines/F3_fifth_voice_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '2fixed local voices;370native frames;inverse/FLOAT/fullmean-cov;12x14C sparse;independent PSD/CSD;2plots',
    'Residualrho audit unresolved;all failures kept;650C-H76voices/F2 exact;no live/hearing/state promotion',
    'research/F3五挡局部声线V1.md | research/F3_fifth_voice_v1_summary.json',
    'baselines/F3_fifth_voice_v1/validation.json'])
print(result)
