"""Freeze reference-selection correction, native coverage and rejected chirplet path."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
base = a.workspace / 'references/analysis'
root = a.workspace / 'baselines/accel_reference_selection_v1'
if a.stage == 'verify':
    verify(root)
    print('Combined reference-selection freeze verified.')
    raise SystemExit

invariant = a.workspace / 'baselines/idle_microtexture_c_v1/inputs'
C = load(invariant / 'C_files_sha256.json')
voices = load(invariant / 'voice_files_sha256.json')
assert len(C) == 612 and len(voices) == 67
for name, h in {**C, **voices}.items():
    assert sha(repo / name) == h, name
wide = base / 'accel_wideband_v1'
coverage = base / 'accel_coverage_v1'
full = base / 'accel_full_inventory_v1'
failed = load(wide / 'observe1/report.json')
diagnosed = load(wide / 'diagnose2/report.json')
assert failed['result'] == 'failed' and failed['error'] == 'AssertionError()'
assert diagnosed['result'] == 'original_control_failure_reproduced_no_source_chirplet_analysis'
assert diagnosed['cases']['moving_native']['high_true_matches'] == 64
assert diagnosed['cases']['moving_compensated']['high_true_matches'] == 64
assert not diagnosed['qualification_passed'] and not diagnosed['source_audio_read']
assert not (wide / 'diagnose1/report.json').exists()
assert len(list((wide / 'diagnose1').glob('*.npz'))) == 8
assert sha(repo / 'tools/accel_wideband_v1/checks.py') == diagnosed['original_source_sha256']
old_audit = load(coverage / 'audit1/report.json')
assert old_audit['result'] == 'all48_native_models_band_powers_and_signed_interference_verified'
new = load(full / 'observe1/report.json')
audited = load(full / 'audit1/report.json')
assert new['result'] == 'full_original_reference_native_fits_complete'
assert audited['result'] == 'all_original_inventory_native_fits_maps_and_coverage_verified'
assert sha(full / 'observe1/report.json') == audited['input_report_sha256']
assert audited['windows'] == 55 and audited['lines'] == 1189
assert [row['successful'] for row in audited['summaries']] == [9, 11, 19]
assert [len(row['dominant_eligible_tiles']) for row in audited['summaries']] == [9, 10, 16]
assert sum(row['eligible_lines'] for row in audited['summaries']) == 470
assert not new['source_chirplet_run'] and not new['audio_or_profile_exported']
for name in ['coverage_correction.png', 'dominant_observations.png']:
    assert sha(full / 'plot1' / name) == load(full / 'plot1/report.json')['images'][name]
assert sha(full / 'audit1/report.json') == load(full / 'plot1/report.json')['audit_report_sha256']

sources = set()
for path in [wide / 'observe1/report.json', coverage / 'observe1/report.json', full / 'observe1/report.json']:
    r = load(path)
    for name, h in r['sources'].items():
        assert sha(path.parent / 'exact_sources' / name) == h == sha(repo / name), name
        sources.add(name)
sources.update([
    'tools/diagnose_accel_wideband_v1.py', 'tools/audit_accel_coverage_v1.py',
    'tools/plot_accel_coverage_v1.py', 'tools/audit_accel_full_inventory_v1.py',
    'tools/plot_accel_full_inventory_v1.py', 'tools/package_accel_reference_selection_v1.py',
    'research/加速主声线漏选修正V1.md', 'research/accel_reference_selection_v1_coverage.png',
    'research/accel_reference_selection_v1_dominant.png', 'AGENTS.md',
    'handoff/研究续接.md', 'handoff/开发留痕.md',
])
for source, target in [('coverage_correction.png', 'coverage'), ('dominant_observations.png', 'dominant')]:
    shutil.copy2(full / 'plot1' / source, repo / f'research/accel_reference_selection_v1_{target}.png')

# Keep a named consolidation as well as the immutable baseline; never delete executed evidence.
evidence = base / 'accel_reference_selection_v1/package1'
evidence.mkdir(parents=True, exist_ok=False)
for name in ['accel_wideband_v1', 'accel_coverage_v1', 'accel_full_inventory_v1']:
    shutil.copytree(base / name, evidence / name)
save(evidence / 'recovered_diagnose1_failure.json', dict(
    metadata_kind='post_execution_recovery_note_NOT_original_run_report',
    original_run='accel_wideband_v1/diagnose1',
    error='TypeError: Object of type int64 is not JSON serializable',
    evidence='Eight saved NPZ and original executed_diagnosis.py; original report.json absent.',
    comparison='diagnose2 changes only JSON count conversion and reproduces unchanged original control assertion.',
    original_script_sha256=sha(wide / 'diagnose1/executed_diagnosis.py'),
    corrected_script_sha256=sha(wide / 'diagnose2/executed_diagnosis.py'),
))
inputs = {
    'C_files_sha256.json': invariant / 'C_files_sha256.json',
    'voice_files_sha256.json': invariant / 'voice_files_sha256.json',
    'data_workspace_AGENTS.md': a.workspace / 'AGENTS.md',
}
validation = dict(
    schema='vsl.accel-reference-selection-freeze/1',
    result='omitted_dominant_native_references_corrected_NOT_new_voice',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    original_all48_windows_preserved=True, original_fit_bounds_and_gates_unchanged=True,
    original_full_inventory_restored=True, previous_cutoff_hz=300,
    successful_windows=39, total_windows=48, eligible_lines=470,
    known_and_real_windows_audited=55, fitted_lines_audited=1189,
    maximum_waveform_error=audited['maximum_waveform_error'],
    maximum_support_error=audited['maximum_support_error'],
    maximum_power_error=audited['maximum_power_error'],
    summaries=audited['summaries'], chirplet_qualification=False,
    source_chirplet_run=False, rejected_and_failed_diagnoses_preserved=True,
    both_plots_viewed=True, C_H_unchanged=612, old_voices_unchanged=67,
    old61_driving_tests_repeated=False, new_audio_or_profile=False,
    runtime_or_default_changed=False, idle_candidate_unchanged_and_pending=True,
    new_listening_question=False, engine_common_phase_or_RPM_load=False,
    previous_amplitude_study_does_not_qualify_new_dominant_modes=True,
    next='Priority remains idle candidate listening. For acceleration, source-only transfer for new dominant modes, fit failures and omitted LF/HF before any full voice.',
)
result = freeze(root, repo, list(sources), evidence, inputs, validation)
verify(root)
save(repo / 'research/accel_reference_selection_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', [
    'accel_reference_selection_v1', 'baselines/accel_reference_selection_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    'Original48 native coverage; restore original inventory;55windows1189lines independent; preserve failed chirplet/control/JSON',
    '39of48 optimizer success;NOT audio/RPM/load/commonphase;612C-H67voices unchanged;idle listening pending',
    'research/加速主声线漏选修正V1.md | research/accel_reference_selection_v1_summary.json',
    'baselines/accel_reference_selection_v1/validation.json',
])
print(result)
