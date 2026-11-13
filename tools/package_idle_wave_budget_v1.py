"""Freeze actual wave budgets, direct-mapping limitations and independent diagnostics."""
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
root = a.workspace/'baselines/idle_wave_budget_v1'
if a.stage == 'verify':
    verify(root); print('Complete actual-wave budget evidence verified.'); raise SystemExit
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np

evidence = a.workspace/'references/analysis/idle_wave_budget_v1'
observed = load(evidence/'observe2/report.json'); audit = load(evidence/'audit1/report.json')
diagnostic = load(evidence/'diagnose1/report.json'); daudit = load(evidence/'diagnostic_audit1/report.json')
plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'all_actual_preinnovation_wave_budgets_complete_NO_sound_promotion'
assert audit['result'] == 'all8_wave_cases_15partition_and_independent_convolution_verified'
assert daudit['result'] == 'all_source_runtime_input_response_diagnostics_independently_verified'
assert audit['input_report_sha256'] == daudit['input_report_sha256'] == plot['input_report_sha256'] == diagnostic['input_report_sha256'] == sha(evidence/'observe2/report.json')
assert daudit['diagnostic_report_sha256'] == plot['diagnostic_report_sha256'] == sha(evidence/'diagnose1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit1/report.json')
assert plot['diagnostic_audit_sha256'] == sha(evidence/'diagnostic_audit1/report.json')
assert audit['curves'] == 80 and audit['lag_points'] == 6480 and len(observed['cases']) == 8
assert audit['original_stationary_full_curve_error'] < 1e-8
assert daudit['all6_input_pairs_positive_all4portions'] and daudit['same2_output_pairs_negative_bothblocks']
failed = load(evidence/'observe1/report.json')
assert failed['result'] == 'failed' and 'Warmup must cover' in failed['error']
for name, digest in failed['sources'].items(): assert sha(evidence/'observe1/exact_sources'/name) == digest
with np.load(evidence/'observe1/architecture.npz') as archive:
    assert int(archive['warmup']) == 48000 and archive['h'].shape[-1] == 65536
with np.load(evidence/'observe2/architecture.npz') as archive: assert int(archive['warmup']) == 65535
for row in observed['cases']:
    assert sha(evidence/'observe2'/row['file']) == row['sha256']
for block in range(2):
    case = next(v for v in observed['cases'] if v['amount'] == 1 and v['block'] == block and v['distribution'] == 'sparse')
    cross = [1, 2, 3, 5, 6, 8]
    assert sum(case['late8_to20ms_mean'][j] < 0 for j in cross) == 5
assert all(.31 < v < .39 for v in plot['sparse_2to4k_zero_relative_increase'])
sources = set()
for folder, report in [('observe2', observed), ('diagnose1', diagnostic)]:
    for name, digest in report['sources'].items():
        assert sha(repo/name) == digest == sha(evidence/folder/'exact_sources'/name); sources.add(name)
for folder, name, executed in [('audit1', 'audit_idle_wave_budget_v1.py', 'executed_auditor.py'),
                               ('diagnostic_audit1', 'audit_idle_wave_diagnostic_v1.py', 'executed_auditor.py'),
                               ('plot1', 'plot_idle_wave_budget_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/name) == sha(evidence/folder/executed); sources.add('tools/'+name)
assert len(plot['images']) == 4
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file']) == image['sha256']
    name = 'research/idle_wave_budget_v1_'+image['file']; shutil.copy2(evidence/'plot1'/image['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_wave_budget_v1.py', 'research/怠速实际声源预算V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
inputs = dict(data_workspace_AGENTS=a.workspace/'AGENTS.md'); tables = {}
for name, digest in observed['parent_manifests'].items():
    path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
    inputs[name+'_manifest.json'] = path
    tables[name] = {row['path']: row['sha256'] for row in load(path)['files']}
for report in [observed, diagnostic, plot]:
    for path, digest in report['inputs'].items():
        assert sha(path) == digest
        resolved = Path(path).resolve()
        if resolved.is_relative_to(evidence.resolve()):
            # Current-stage inputs are already copied with the complete evidence tree.
            continue
        relative = resolved.relative_to((a.workspace/'baselines').resolve())
        if len(relative.parts) == 2 and relative.parts[1] == 'manifest.json':
            if relative.parts[0] not in tables:
                inputs[relative.parts[0]+'_manifest.json'] = path
                tables[relative.parts[0]] = {row['path']: row['sha256'] for row in load(path)['files']}
        else:
            assert digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    path = a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name
    values = load(path); assert len(values) == count
    for source, digest in values.items(): assert sha(repo/source) == digest, source
    inputs[name] = path
validation = dict(schema='vsl.idle-wave-budget-freeze/1',
    result='direct_PREinnovation_q_mapping_NOT_supported_as_complete_idle_solution',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, diagnostic_audit=daudit, cases=8, curves=80, lag_points=6480,
    ensemble_time_origin_NOT_random_record_estimator=True, all7_terms_and_raw_moments_retained=True,
    direct_input_q_positive_but_filter_output_two_pairs_reverse=True,
    new_sparse_late_cross_negative_pairs=5, original_source_negative_pairs=6,
    sparse_2to4k_zero_relative_increase=plot['sparse_2to4k_zero_relative_increase'],
    own_band_energy_centroid_ms_NOT_compensation_delay=plot['own_band_energy_centroid_ms'],
    first_attempt_warmup_failure_and_original_plan_preserved=True,
    analysis_pre_history_only_amended_no_profile_or_fit_change=True,
    posthoc_diagnostic_separately_declared_and_verified=True, all4_complete_plots_viewed=True,
    unchanged_C_H=612, unchanged_old_voices=67, old61_driving_tests_repeated=False,
    generated_random_audio=False, runtime_changed=False, source_RPM_phase_or_timbre_accepted=False,
    original_common_phase_qualification_still_required=True,
    next='Known-qualified modulation-energy response transfer and post-resonance amplitude placement versus actual forward input solve; validate final output then jointly allocate periodic/independent fourth budgets. No hand delay/HF/phase lock/oldkappa addition; existing hearing pending/no duplicate or blind C promotion.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_wave_budget_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_wave_budget_v1', 'baselines/idle_wave_budget_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    'Exact3ensembles/8cases80curves6480points;independent OA+15partitions/filter/diagnosticBessel',
    'Preinnovation directq distorts linkage/doublekappa;ensemble-time not empirical estimator;612C-H67voices unchanged',
    'research/怠速实际声源预算V1.md | research/idle_wave_budget_v1_summary.json',
    'baselines/idle_wave_budget_v1/validation.json'])
print(result)
