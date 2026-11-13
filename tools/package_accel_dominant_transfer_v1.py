"""Freeze all six corrected-primary transfers, independent audit and exclusions."""
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
evidence = a.workspace / 'references/analysis/accel_dominant_transfer_v1'
root = a.workspace / 'baselines/accel_dominant_transfer_v1'
if a.stage == 'verify':
    verify(root)
    print('Dominant transfer freeze verified.')
    raise SystemExit
observed = load(evidence / 'observe1/report.json')
audit = load(evidence / 'audit1/report.json')
plot = load(evidence / 'plot1/report.json')
assert observed['result'] == 'all6_corrected_dominant_transfers_complete'
assert audit['result'] == 'all3_source_models_full_graphs_and6_dominant_transfers_verified'
assert audit['source_models'] == 3 and audit['predicted_rows'] == 51 and audit['outside_rows'] == 19
assert sha(evidence / 'observe1/report.json') == audit['input_report_sha256'] == plot['input_report_sha256']
assert sha(evidence / 'audit1/report.json') == plot['audit_report_sha256']
assert len(observed['pairs']) == 6
assert all(v['status'] == 'compared' and v['maps_to_target_primary'] and all(v['both_diagnostics_pass'].values()) for v in observed['pairs'])
assert sum(v['median_absolute_error_db']['log_linear'] < v['median_absolute_error_db']['geometric'] for v in observed['pairs']) == 1
sources = list(observed['sources'])
for name, h in observed['sources'].items():
    assert sha(repo / name) == h == sha(evidence / 'observe1/exact_sources' / name)
for name, h in observed['input_hashes'].items():
    assert sha(name) == h
invariants = a.workspace / 'baselines/idle_microtexture_c_v1/inputs'
inputs = {'data_workspace_AGENTS.md': a.workspace / 'AGENTS.md'}
for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    table = load(invariants / filename)
    assert len(table) == count
    for name, h in table.items():
        assert sha(repo / name) == h
    inputs[filename] = invariants / filename
for folder in ['accel_reference_selection_v1', 'accel_ridges_v1', 'accel_amplitude_v1']:
    inputs[folder + '_manifest.json'] = a.workspace / 'baselines' / folder / 'manifest.json'
inputs['prior_scale_audit.json'] = a.workspace / 'baselines/accel_amplitude_v1/evidence/audit1/report.json'
for filename in observed['input_hashes']:
    path = Path(filename)
    assert path.resolve().is_relative_to((a.workspace / 'baselines').resolve())
    inputs['parents/' + path.relative_to(a.workspace / 'baselines').as_posix()] = path
for name, target in [('dominant_errors.png', 'errors'), ('dominant_laws.png', 'laws')]:
    assert sha(evidence / 'plot1' / name) == plot['images'][name]
    shutil.copy2(evidence / 'plot1' / name, repo / f'research/accel_dominant_transfer_v1_{target}.png')
sources += ['tools/audit_accel_dominant_transfer_v1.py', 'tools/plot_accel_dominant_transfer_v1.py',
            'tools/package_accel_dominant_transfer_v1.py', 'research/加速最强声线跨片段验证V1.md',
            'research/accel_dominant_transfer_v1_errors.png', 'research/accel_dominant_transfer_v1_laws.png',
            'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md']
validation = dict(schema='vsl.accel-dominant-transfer-freeze/1', result='all6_primary_conditional_transfers_pass_old_diagnostics',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    source_models=3, source_training_rows=35, source_domain_predictions=51, outside_rows_retained=19,
    pairs=audit['pairs'], all6_full_inventory_maps_to_target_primary=True,
    all6_all3laws_pass_original_diagnostics=True, loglinear_better_than_geometric_pairs=1,
    maximum_model_error=audit['maximum_model_error'], maximum_prediction_error=audit['maximum_prediction_error'],
    original_known_controls_and_dominant_missing_adjacent_preserved=True,
    parent_input_files_manifest_verified=True, prior_native_scale_reused=True,
    new_alignment_search=False, target_amplitude_training=False, target_gain_correction=False,
    allpassages_previously_inspected=True, target_eligibility_and_guide_observed=True,
    pristine_holdout=False, common_phase_RPM_load_or_source_identity=False,
    original_common_phase_qualification_required=True, complete_acceleration=False,
    new_audio_or_profile=False, runtime_or_default_changed=False,
    C_H_unchanged=612, old_voices_unchanged=67, old61_tests_repeated=False,
    both_plots_viewed=True, idle_candidate_pending_and_question_not_repeated=True,
    next='Check omitted low-frequency structure and fixed/non-tonal components before a complete layered acceleration recipe; preserve simple amplitude controls and avoid inventing RPM/load laws.')
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo / 'research/accel_dominant_transfer_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', [
    'accel_dominant_transfer_v1', 'baselines/accel_dominant_transfer_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '3source-only dominant models;6full-inventory pairs;51predictions19outside;independent scalar and parent-manifest audit',
    'All old primary diagnostics pass;loglinear better1of6;NOT fullaccel/RPM/load/commonphase;612C-H67voices unchanged',
    'research/加速最强声线跨片段验证V1.md | research/accel_dominant_transfer_v1_summary.json',
    'baselines/accel_dominant_transfer_v1/validation.json',
])
print(result)
