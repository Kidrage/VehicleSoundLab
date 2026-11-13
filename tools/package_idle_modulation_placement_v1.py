"""Freeze placement evidence without changing accepted C or voice artifacts."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
root = a.workspace/'baselines/idle_modulation_placement_v1'
if a.stage == 'verify':
    verify(root); print('Complete placement evidence verified.'); raise SystemExit
evidence = a.workspace/'references/analysis/idle_modulation_placement_v1'
observed = load(evidence/'observe1/report.json'); audit = load(evidence/'audit1/report.json')
plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'all64_paired_placement_power_observations_complete_NO_timbre_claim'
assert audit['result'] == 'all64paired_renders_known_and_crossseed_statistics_verified' and audit['seeds'] == 64
assert audit['input_report_sha256'] == plot['input_report_sha256'] == sha(evidence/'observe1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit1/report.json')
assert observed['all_pointwise_pre_coverage'] == observed['number_pre_checks'] == 36
assert len(observed['observations']) == 4 and len(observed['paired_post_minus_pre']) == 2
for difference in observed['paired_post_minus_pre']: assert all(v < 0 for v in difference['mse_family_high'])
assert sha(evidence/'observe1'/observed['data_file']) == observed['data_sha256']
sources = set()
for name, digest in observed['sources'].items():
    assert sha(repo/name) == digest == sha(evidence/'observe1/exact_sources'/name); sources.add(name)
for directory, name, executed in [('audit1', 'audit_idle_modulation_placement_v1.py', 'executed_auditor.py'),
                                  ('plot1', 'plot_idle_modulation_placement_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/name) == sha(evidence/directory/executed); sources.add('tools/'+name)
assert len(plot['images']) == 1
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file']) == image['sha256']
    name = 'research/idle_modulation_placement_v1_'+image['file']
    shutil.copy2(evidence/'plot1'/image['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_modulation_placement_v1.py', 'research/怠速细节调幅位置V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
inputs = dict(data_workspace_AGENTS=a.workspace/'AGENTS.md'); tables = {}
for name, digest in observed['parent_manifests'].items():
    path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
    inputs[name+'_manifest.json'] = path
    tables[name] = {row['path']: row['sha256'] for row in load(path)['files']}
for path, digest in observed['inputs'].items():
    relative = Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
    assert sha(path) == digest == tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    path = a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name; values = load(path)
    assert len(values) == count
    for source, digest in values.items(): assert sha(repo/source) == digest, source
    inputs[name] = path
validation = dict(schema='vsl.idle-modulation-placement-freeze/1',
    result='POSTresonance_supported_for_q_tracking_NOT_total_wave_or_timbre',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, paired_seeds=64, source='F2_tailpipe_frozen_positive_power',
    full6s_both3s_1ms_powers=True, all64_arrays_independently_rerendered=True,
    independent_crossseed_estimators_and_all_jackknife_verified=True,
    all8_MSE_contrasts_approx_family95_upper_negative=True, no_seed_selection=True,
    mse_relative_reductions=plot['mse_relative_reductions'], pre_exact_coverage_descriptive=36,
    all6_post_correlations_positive_bothblocks=True, complete_figure_viewed=True,
    conditional_random_power_NOT_total_separation_or_fourth_budget=True,
    post_is_MC_estimate_NOT_exact_LTV=True, unchanged_C_H=612, unchanged_old_voices=67,
    new_WAV=False, runtime_changed=False, old61_driving_tests_repeated=False,
    next='Qualify actual POST+main total-power and jointly allocate periodic/innovation fourth budgets; no blind oldkappa add. Existing hearing pending/no duplicate or C promotion. Original commonphase qualification and full goal remain.')
for row in observed['observations']:
    if row['placement'] == 'post': assert all(v > 0 for v in row['point'][12:])
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_modulation_placement_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_modulation_placement_v1', 'baselines/idle_modulation_placement_v1/manifest.json',
    result['file_count'], result['manifest_sha256'],
    'Known binary/basis;all64paired OA/directbiquad renders;crossseed/jackknife/8approxBonferroni;PREexact',
    'POST qtracking supported;not total-q separation/4th/timbre;612C-H67voices unchanged',
    'research/怠速细节调幅位置V1.md | research/idle_modulation_placement_v1_summary.json',
    'baselines/idle_modulation_placement_v1/validation.json'])
print(result)
