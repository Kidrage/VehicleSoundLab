"""Freeze predictive success, negative global phase witness and all executed attempts."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
root = a.workspace/'baselines/idle_phase_difference_v1'
if a.stage == 'verify':
    verify(root); print('Complete phase-difference evidence verified.'); raise SystemExit
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np

evidence = a.workspace/'references/analysis/idle_phase_difference_v1'
observed = load(evidence/'observe2/report.json')
audit = load(evidence/'audit1/report.json')
bounds = load(evidence/'bound1/report.json')
baudit = load(evidence/'bound_audit1/report.json')
plot = load(evidence/'plot2/report.json')
assert observed['result'] == 'all_nested_phase_difference_observations_complete'
assert audit['result'] == 'all_nested_features_models_and_800_direct_lag_curves_verified'
assert bounds['result'] == 'dependent_phase_bounds_complete_no_sound_promotion'
assert baudit['result'] == 'all10_models_full32768point_bounds_independently_verified'
assert audit['input_report_sha256'] == baudit['input_report_sha256'] == plot['input_report_sha256'] == sha(evidence/'observe2/report.json')
assert baudit['bound_report_sha256'] == plot['bound_report_sha256'] == sha(evidence/'bound1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit1/report.json')
assert plot['bound_audit_sha256'] == sha(evidence/'bound_audit1/report.json')
assert audit['curves'] == 800 and audit['observations'] == 16
assert not observed['future_synthesis_prerequisite'] and observed['supported_bands'] == [True]*4
assert not bounds['original_gate_unchanged']
assert bounds['observations'][0]['certificate']['status'] == ['positive_bound', 'negative_counterexample', 'positive_bound', 'positive_bound']
real = observed['observations'][0]
assert .167 < real['assessment']['expanded']['check']['minimum_prediction'][1] < .168
assert -.322 < bounds['observations'][0]['certificate']['grid_minimum'][1] < -.321
assert bounds['observations'][0]['certificate']['grid_argmin_indices'][1] == [7, 25, 2]
for part in ['train', 'check']:
    assert np.all(np.asarray(real['time_budget']['expanded'][part]['prediction_curve_rmse']) <
                  np.asarray(real['time_budget']['native'][part]['prediction_curve_rmse']))
sources = set()
for folder, report in [('observe2', observed), ('bound1', bounds)]:
    for name, digest in report['sources'].items():
        assert sha(repo/name) == digest == sha(evidence/folder/'exact_sources'/name)
        sources.add(name)
for folder, name, executed in [
    ('audit1', 'audit_idle_phase_difference_v1.py', 'executed_auditor.py'),
    ('bound_audit1', 'audit_idle_phase_difference_bounds_v1.py', 'executed_auditor.py'),
    ('plot2', 'plot_idle_phase_difference_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/name) == sha(evidence/folder/executed)
    sources.add('tools/'+name)
failure = load(evidence/'observe1/report.json')
assert failure['result'] == 'failed' and failure['error'] == 'AssertionError()'
for name, digest in failure['sources'].items():
    assert sha(evidence/'observe1/exact_sources'/name) == digest
for row in observed['observations']:
    assert sha(evidence/'observe2'/row['file']) == row['sha256']
assert len(plot['images']) == 3 and len(load(evidence/'plot1/report.json')['images']) == 3
for image in plot['images']:
    assert sha(evidence/'plot2'/image['file']) == image['sha256']
    name = 'research/idle_phase_difference_v1_'+image['file']
    shutil.copy2(evidence/'plot2'/image['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_phase_difference_v1.py', 'research/怠速相位差与颗粒V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
inputs = dict(data_workspace_AGENTS=a.workspace/'AGENTS.md'); tables = {}
for name, digest in observed['parent_manifests'].items():
    path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
    inputs[name+'_manifest.json'] = path
    tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}
for path, digest in observed['inputs'].items():
    relative = Path(path).relative_to(a.workspace/'baselines')
    assert sha(path) == digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    path = a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name
    values = load(path); assert len(values) == count
    for source, digest in values.items(): assert sha(repo/source) == digest, source
    inputs[name] = path
validation = dict(schema='vsl.idle-phase-difference-freeze/1',
    result='predictive_difference_features_but_unsafe_linear_power_NO_sound_promotion',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, bound_audit=baudit, full_grid_models=10, source_control_models=4,
    check_incremental_improvement=real['incremental_check_improvement'],
    check_all4_bands_beat_every_samePSD_control=True, original_synthesis_prerequisite=False,
    real_negative_phase_witness=bounds['observations'][0]['certificate'],
    all10_curves_both_portions_closer_but_not_recovered=True,
    complete_power_covariance_budget_is_NOT_generated_waveform_cumulant=True,
    failed_observe1_and_summation_only_correction_preserved=True,
    both_plot_attempts_preserved_and_final_complete_viewed=True,
    unchanged_C_H=612, unchanged_old_voices=67, old61_driving_tests_repeated=False,
    new_audio_or_runtime_profile=False, runtime_changed=False, physical_source_or_common_crank_qualified=False,
    original_common_phase_qualification_still_required=True,
    next='Declared intrinsically-positive conditional power model; known/TRAIN-only/check/allcontrols and actual filtered waveform budgets before synthesis. Existing hearing pending/no duplicate/blind C promotion.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_phase_difference_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_phase_difference_v1', 'baselines/idle_phase_difference_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    'TRAINonly/nested4groups;800curves81lags/QR/products;10models full32768grid/negativewitness',
    'Check prediction improves but2.2-4k actual negative phase;no audio/C/profile;612C-H67voices unchanged',
    'research/怠速相位差与颗粒V1.md | research/idle_phase_difference_v1_summary.json',
    'baselines/idle_phase_difference_v1/validation.json'])
print(result)
