"""Freeze the sustained-coordinate diagnostic without altering any source recipe."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]; root = a.workspace/'baselines/idle_phase_transfer_v1'
if a.stage == 'verify': verify(root); print('Complete180s phase transfer archive verified.'); raise SystemExit
evidence = a.workspace/'references/analysis/idle_phase_transfer_v1'
observed = load(evidence/'observe1/report.json'); audit = load(evidence/'audit1/report.json'); plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'all180s_power_phase_transfer_observed_NO_recipe_change'
assert audit['result'] == 'all60_native_blocks_and_both_recorded_phase_portions_verified'
assert plot['result'] == 'complete180s_phase_transfer_plots'
assert audit['input_report_sha256'] == plot['input_report_sha256'] == sha(evidence/'observe1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit1/report.json')
assert len(observed['runtime']) == 60 and len(observed['source_observations']) == 2
assert observed['first12s_previous_q_error'] < 1e-12 and not observed['audio_generated'] and not observed['runtime_changed']
assert sha(evidence/'observe1'/observed['data_file']) == observed['data_sha256']
for row in observed['source_observations']: assert sha(evidence/'observe1'/row['file']) == row['sha256']
assert sha(evidence/'plot1/metrics.json') == plot['metrics_sha256']
sources = set()
for name, digest in observed['sources'].items():
    assert sha(repo/name) == digest == sha(evidence/'observe1/exact_sources'/name); sources.add(name)
for directory, source, executed in [('audit1', 'audit_idle_phase_transfer_v1.py', 'executed_auditor.py'),
                                     ('plot1', 'plot_idle_phase_transfer_v1.py', 'executed_plot.py')]:
    assert sha(repo/'tools'/source) == sha(evidence/directory/executed); sources.add('tools/'+source)
assert len(plot['images']) == 2
for row in plot['images']:
    assert sha(evidence/'plot1'/row['file']) == row['sha256']
    name = 'research/idle_phase_transfer_v1_'+row['file']; shutil.copy2(evidence/'plot1'/row['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_phase_transfer_v1.py', 'research/怠速持续相位迁移V1.md',
                'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
inputs = dict(data_workspace_AGENTS=a.workspace/'AGENTS.md'); tables = {}
for name, digest in observed['parent_manifests'].items():
    path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
    inputs[name+'_manifest.json'] = path; tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}
for path, digest in observed['inputs'].items():
    rel = Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
    assert sha(path) == digest == tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    path = a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name; entries = load(path); assert len(entries) == count
    for source, digest in entries.items(): assert sha(repo/source) == digest
    inputs[name] = path
validation = dict(schema='vsl.idle-phase-transfer-freeze/1', result='sustained_coordinate_distribution_drift_observed',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(), audit=audit,
    all60_native_blocks=True, seconds=180, all180000_1msmeans=True, source_portions=2,
    detuning_hz=observed['detuning_hz'], closure_period_seconds=observed['closure_period_seconds'],
    recorded_closure_resultants=[row['resultant'][-1] for row in observed['source_observations']],
    full180s_closure_resultant=observed['full180s']['resultant'][-1], all_figures_viewed=True,
    physical_phase_or_RPM_claim=False, audio_generated=False, listening_accepted=False,
    unchanged_C_H=612, unchanged_old_voices=67, runtime_changed=False, old61_driving_tests_repeated=False,
    next='Learn recorded closure distribution/dynamics and relationship to detail power before any sustained-coordinate correction. No arbitrary phase lock/frequency change/copied trajectory/gain compensation. Prior audiblecandidate pending; preserve commonphase/fullgoal.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_phase_transfer_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_phase_transfer_v1', 'baselines/idle_phase_transfer_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    'Native180s60blocks/all1ms/sourceq/realtrig/sortedquantiles/circular;knownfirst/full12sidentity',
    'qcoordinate drift/notwaveform/hearing;612C-H67voicesunchanged',
    'research/怠速持续相位迁移V1.md | research/idle_phase_transfer_v1_summary.json', 'baselines/idle_phase_transfer_v1/validation.json'])
print(result)
