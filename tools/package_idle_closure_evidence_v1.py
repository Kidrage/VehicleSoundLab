"""Freeze source/controls, explicit added coordinate, both audits and all support decisions."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]; root = a.workspace/'baselines/idle_closure_evidence_v1'
if a.stage == 'verify': verify(root); print('Complete closure-source and added-coordinate archive verified.'); raise SystemExit
evidence = a.workspace/'references/analysis/idle_closure_evidence_v1'
observed = load(evidence/'observe1/report.json'); extension = load(evidence/'extension1/report.json')
audit = load(evidence/'audit1/report.json'); extra = load(evidence/'extension_audit1/report.json'); plot = load(evidence/'plot1/report.json')
assert observed['result'] == 'all8_closure_portions_and_shortrecord_counterexample_observed'
assert extension['result'] == 'second_coordinate_and_joint_support_observed_NO_generation'
assert audit['result'] == 'all8_closure_501lag_curves_and180000_arc_decisions_verified'
assert extra['result'] == 'all8_eta_501lag_curves_and180000_joint_decisions_verified'
assert plot['result'] == 'all_source_control_curves_and_joint_support_plotted'
for row in [extension, audit, extra, plot]: assert row['input_report_sha256'] == sha(evidence/'observe1/report.json')
for row in [extra, plot]: assert row['extension_report_sha256'] == sha(evidence/'extension1/report.json')
assert plot['audit_sha256'] == sha(evidence/'audit1/report.json')
assert plot['extension_audit_sha256'] == sha(evidence/'extension_audit1/report.json')
assert len(observed['observations']) == len(extension['observations']) == 8
for directory, report in [('observe1', observed), ('extension1', extension)]:
    for row in report['observations']: assert sha(evidence/directory/row['file']) == row['sha256']
assert sha(evidence/'observe1'/observed['runtime_arc_file']) == observed['runtime_arc_sha256']
assert sha(evidence/'extension1'/extension['runtime_file']) == extension['runtime_sha256']
sources = set()
for name, digest in observed['sources'].items():
    assert sha(repo/name) == digest == sha(evidence/'observe1/exact_sources'/name); sources.add(name)
for directory, source, executed in [('audit1', 'tools/audit_idle_closure_evidence_v1.py', 'executed_auditor.py'),
    ('extension1', 'tools/extend_idle_closure_coordinates_v1.py', 'executed_extension.py'),
    ('extension1', 'research/idle_closure_coordinates_v1_extension.json', 'executed_extension_plan.json'),
    ('extension_audit1', 'tools/audit_idle_closure_coordinates_v1.py', 'executed_extension_auditor.py'),
    ('plot1', 'tools/plot_idle_closure_evidence_v1.py', 'executed_plot.py')]:
    assert sha(repo/source) == sha(evidence/directory/executed); sources.add(source)
assert len(plot['images']) == 2
for row in plot['images']:
    assert sha(evidence/'plot1'/row['file']) == row['sha256']
    name = 'research/idle_closure_evidence_v1_'+row['file']; shutil.copy2(evidence/'plot1'/row['file'], repo/name); sources.add(name)
sources.update(['tools/package_idle_closure_evidence_v1.py', 'research/怠速相位关联证据V1.md',
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
validation = dict(schema='vsl.idle-closure-evidence-freeze/1', result='two_relative_coordinate_source_evidence_NOT_phase_lock_identification',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, extension_audit=extra, all16portions_all501lags=True, all180000_joint_decisions=True,
    additional_eta_is_explicit_posthoc_diagnostic=True, source_check_joint_coverage=extension['source_joint_check_coverage'],
    runtime_first12s_joint_coverage=extension['runtime_joint_first12_coverage'], runtime180s_joint_coverage=extension['runtime_joint_coverage'],
    independent_short_record_counterexample=True, phase_observer_known_cases=6,
    longterm_stationary_coupling_identified=False, all_figures_viewed=True, empirical_arc_NOT_confidence_region=True,
    unchanged_C_H=612, unchanged_old_voices=67, runtime_changed=False, audio_generated=False, listening_accepted=False,
    next='Propose explicit two-relative-coordinate statistical texture hypothesis, not hardlock/copiedphase. Known+crossportion/fullwave/longrun before audible candidate; original commonphase qualification and fullgoal remain. Prior hearing pending/no duplicate.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation); verify(root)
save(repo/'research/idle_closure_evidence_v1_summary.json', dict(validation, **result))
append_index(repo/'handoff/阶段索引.csv', ['idle_closure_evidence_v1', 'baselines/idle_closure_evidence_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    '8psi+8eta/all501lags/180000joint;knownphaseobserver6/independentdetunecounterexample/fullsourceq',
    'RelativecoordnotlockID/explicitposthoceta;612C-H67voicesunchanged',
    'research/怠速相位关联证据V1.md | research/idle_closure_evidence_v1_summary.json', 'baselines/idle_closure_evidence_v1/validation.json'])
print(result)
