"""Archive positive sample-power model, all outcomes and numerical audit correction."""
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
root = a.workspace/'baselines/idle_positive_power_v1'
if a.stage == 'verify':
    verify(root); print('Complete positive idle-power evidence verified.'); raise SystemExit
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np

evidence = a.workspace/'references/analysis/idle_positive_power_v1'
observed = load(evidence/'observe1/report.json')
audit = load(evidence/'audit2/report.json'); failed = load(evidence/'audit1/report.json')
plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'all_positive_sample_power_models_observed'
assert audit['result'] == 'all8_positive_models32_KKT_fits_and800_lag_curves_verified'
assert audit['models'] == 8 and audit['band_fits'] == 32 and audit['curves'] == 800
assert audit['input_report_sha256'] == plot['input_report_sha256'] == sha(evidence/'observe1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit2/report.json')
assert failed['result'] == 'failed' and failed['error'] == 'AssertionError()'
assert observed['future_synthesis_prerequisite'] and observed['supported_bands'] == [True]*4
assert audit['maximum_KKT_gradient'] < 1e-9 and audit['minimum_hessian_eigenvalue'] > 0
assert audit['maximum_reference_relative_error'] < 2e-14
real = observed['observations'][0]
for row in observed['observations']:
    assert sha(evidence/'observe1'/row['file']) == row['sha256']
    for model in row['models'].values():
        assert model['converged'] and model['full_rank'] and model['bounds']['finite_normal_bounds']
        assert np.all(np.asarray(model['bounds']['power_lower']) > 0)
for part in ['train', 'check']:
    assert np.all(np.asarray(real['time_budget']['expanded'][part]['prediction_curve_rmse']) <
                  np.asarray(real['time_budget']['native'][part]['prediction_curve_rmse']))
sources = set()
for name, digest in observed['sources'].items():
    assert sha(repo/name) == digest == sha(evidence/'observe1/exact_sources'/name); sources.add(name)
for folder, name, executed in [('audit2', 'audit_idle_positive_power_v1.py', 'executed_auditor.py'),
                               ('plot1', 'plot_idle_positive_power_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/name) == sha(evidence/folder/executed); sources.add('tools/'+name)
assert sha(evidence/'audit1/executed_auditor.py') != sha(evidence/'audit2/executed_auditor.py')
assert len(plot['images']) == 3
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file']) == image['sha256']
    name = 'research/idle_positive_power_v1_'+image['file']
    shutil.copy2(evidence/'plot1'/image['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_positive_power_v1.py', 'research/怠速正功率模型V1.md',
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
validation = dict(schema='vsl.idle-positive-power-freeze/1',
    result='positive_power_prediction_preserved_NOT_waveform_or_sound_promotion',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, all8models32fits_converged=True, all4bands_beat_both_native_baselines_and_allcontrols=True,
    new_prediction_prerequisite=True, old_linear_prerequisite_failure_remains=True,
    check_improvement_over_positive_native=real['incremental_check_improvement'],
    check_improvement_over_old_native_OLS=real['check_improvement_over_old_native_OLS'],
    global_expanded_power_bounds=real['models']['expanded']['bounds'],
    full_resolution_exp_before_average=True, all10_curves_both_portions_closer=True,
    check_mean_target=real['assessment']['expanded']['check']['mean_target'],
    check_mean_prediction=real['assessment']['expanded']['check']['mean_prediction'],
    sample_total_power_is_NOT_separated_innovation_gain=True, waveform_budget_proven=False,
    first_audit_failed_reference_roundoff_preserved_only_gamma_n_audit_correction=True,
    model_and_source_not_rerun=True, all3_complete_plots_viewed=True,
    unchanged_C_H=612, unchanged_old_voices=67, old61_driving_tests_repeated=False,
    audio_or_runtime_profile_exported=False, runtime_changed=False,
    original_common_phase_qualification_still_required=True,
    next='Known-qualified actual13OSC+6FIR generated wave variance/time/cumulant budget including main, gain placement and response supports BEFORE new audition/C; existing listening pending/no duplicate/blind promotion.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_positive_power_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_positive_power_v1', 'baselines/idle_positive_power_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    'Knownpositive/8models32KKTfits;fullresolution exp;independent IIR/800curves81lags/globalbounds',
    'SourceTOTALpower not innovationgain/wavebudget;timbre/phase unqualified;612C-H67voices unchanged',
    'research/怠速正功率模型V1.md | research/idle_positive_power_v1_summary.json',
    'baselines/idle_positive_power_v1/validation.json'])
print(result)
