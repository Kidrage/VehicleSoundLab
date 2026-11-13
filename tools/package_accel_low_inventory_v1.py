"""Freeze all low inventories, boundary correction, exact-null failures and audit."""
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
evidence = a.workspace / 'references/analysis/accel_low_inventory_v1'
root = a.workspace / 'baselines/accel_low_inventory_v1'
if a.stage == 'verify':
    verify(root)
    print('Low inventory freeze verified.')
    raise SystemExit
report = load(evidence / 'observe4/report.json')
audit = load(evidence / 'audit4/report.json')
plot = load(evidence / 'plot1/report.json')
assert report['result'] == 'all48_native_low_inventories_and_resolution_observed'
assert audit['result'] == 'all48_native_low_power_descriptors_scanned_peaks_and_graphs_verified'
assert audit['windows'] == 48 and audit['peak_observations'] == 267 and audit['graphs'] == 98
assert sha(evidence / 'observe4/report.json') == audit['input_report_sha256'] == plot['input_report_sha256']
assert sha(evidence / 'audit4/report.json') == plot['audit_report_sha256']
for folder in ['audit1', 'audit2', 'audit3']:
    failed = load(evidence / folder / 'report.json')
    assert failed['result'] == 'failed' and failed['error'].startswith('AssertionError')
    assert (evidence / folder / 'executed_audit.py').is_file()
keys = ['total_power_LR', 'band_power_LR', 'band_fraction_of_full_native_LR', 'descriptors', 'inventory', 'guide', 'tile']
for n in [1, 2, 3, 4]:
    earlier = load(evidence / f'observe{n}/report.json')
    assert earlier['result'] == report['result']
    for name, h in earlier['sources'].items():
        assert sha(evidence / f'observe{n}/exact_sources' / name) == h
    for segment in report['plan']['segments']:
        old = load(evidence / f'observe{n}' / segment / 'observations.json')
        new = load(evidence / 'observe4' / segment / 'observations.json')
        assert old['parent_json_sha256'] == new['parent_json_sha256'] and old['parent_audio_sha256'] == new['parent_audio_sha256']
        assert old['reference_hz'] == new['reference_hz'] and len(old['rows']) == len(new['rows'])
        for before, after in zip(old['rows'], new['rows']):
            assert {k: before[k] for k in keys} == {k: after[k] for k in keys}
sources = list(report['sources'])
for name, h in report['sources'].items():
    assert sha(repo / name) == h
for name, target in [('native_low.png', 'native'), ('low_resolution.png', 'resolution')]:
    assert sha(evidence / 'plot1' / name) == plot['images'][name]
    shutil.copy2(evidence / 'plot1' / name, repo / f'research/accel_low_inventory_v1_{target}.png')
sources += ['tools/audit_accel_low_inventory_v1.py', 'tools/plot_accel_low_inventory_v1.py',
    'tools/package_accel_low_inventory_v1.py', 'research/加速遗漏低频清点V1.md',
    'research/accel_low_inventory_v1_native.png', 'research/accel_low_inventory_v1_resolution.png',
    'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md']
invariants = a.workspace / 'baselines/idle_microtexture_c_v1/inputs'
inputs = {'data_workspace_AGENTS.md': a.workspace / 'AGENTS.md',
          'ridge_manifest.json': a.workspace / 'baselines/accel_ridges_v1/manifest.json'}
for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    values = load(invariants / filename)
    assert len(values) == count
    for name, h in values.items():
        assert sha(repo / name) == h
    inputs[filename] = invariants / filename
for name in report['plan']['segments']:
    inputs[name + '_original_ridges.json'] = a.workspace / 'baselines/accel_ridges_v1/evidence/observe2' / (name + '.json')
validation = dict(schema='vsl.accel-low-inventory-freeze/1', result='omitted_low_inventory_and_crossing200_censoring_audited_NOT_source_profile',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    native_windows=48, real_low_peak_observations=265, including_known_peak_observations=267,
    all4_observations_source_stats_and_low_inventories_exact=True,
    crossing200_observed_union_with_frozen_upper_peaks=True,
    original_floors_and_ranges_separate_and_unchanged=True,
    all3_known_null_normalization_and_prominence_failures_retained=True,
    independent_periodogram_absolute_power=True, independent_formulas_from_saved_exact_cells=True,
    exact_null_normalized_descriptors_not_physically_precise=True,
    original_tolerances_unchanged=True, maximum_power_error=audit['maximum_power_error'],
    maximum_descriptor_error=audit['maximum_descriptor_error'], maximum_peak_error=audit['maximum_peak_error'],
    observations=report['observations'], reference_diagnostics=plot['reference_diagnostics'],
    old_moving_fixed_classifier_used=False, source_identity_or_RPM_load_or_common_phase=False,
    original_common_phase_qualification_remains_required=True, both_plots_viewed=True,
    new_audio_or_runtime_profile=False, runtime_or_default_changed=False,
    C_H_unchanged=612, old_voices_unchanged=67, old61_tests_repeated=False,
    idle_candidate_pending_and_question_not_repeated=True,
    next='Native low candidate joint amplitude/phase fits, fixed+moving neighbours and same-mono noise counterexamples, temporal support and held-window parameter prediction before layered rumble recipe.')
result = freeze(root, repo, sources, evidence, inputs, validation)
verify(root)
save(repo / 'research/accel_low_inventory_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', [
    'accel_low_inventory_v1', 'baselines/accel_low_inventory_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    'All48native low inventories;265real peaks;crossing200 union correction;independent spectra/scanned peaks/98graphs;3null failures retained',
    'No source classification/profile/audio;old dense-comb and commonphase limits remain;612C-H67voices unchanged',
    'research/加速遗漏低频清点V1.md | research/accel_low_inventory_v1_summary.json',
    'baselines/accel_low_inventory_v1/validation.json',
])
print(result)
