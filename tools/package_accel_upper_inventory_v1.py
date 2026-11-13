"""Freeze the upper inventory and temporal evidence, without promoting sound."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=['freeze', 'verify'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = a.workspace / 'baselines/accel_upper_inventory_v1'
if a.stage == 'verify':
    verify(root)
    print('Upper inventory and temporal archive verified.')
    raise SystemExit
evidence = a.workspace / 'references/analysis/accel_upper_inventory_v1'
observed = load(evidence / 'observe1/report.json')
audit = load(evidence / 'audit1/report.json')
known = load(evidence / 'known_check1/report.json')
temporal = load(evidence / 'temporal1/report.json')
temporal_audit = load(evidence / 'temporal_audit1/report.json')
assert observed['result'] == 'all48_upper_inventory_rejection_census_complete'
assert audit['result'] == 'all48_upper_cells_rejections_descriptors_verified'
assert known['result'] == 'all12_known_waveforms_and_outcomes_verified'
assert temporal['result'] == 'all3_passages_and9_phase_controls_observed'
assert temporal_audit['result'] == 'all12_temporal_observations_independently_verified'
assert audit['windows'] == 48 and audit['known'] == known['fixtures'] == 12
assert temporal_audit['observations'] == 12
for item in [audit, known]:
    assert item['input_report_sha256'] == sha(evidence / 'observe1/report.json')
assert temporal_audit['input_report_sha256'] == sha(evidence / 'temporal1/report.json')
sources = set()
for folder, report in [('observe1', observed), ('temporal1', temporal)]:
    for name, digest in report['sources'].items():
        assert sha(repo / name) == digest == sha(evidence / folder / 'exact_sources' / name), name
        sources.add(name)
parent = a.workspace / 'baselines/accel_candidate_prediction_v1'
for report in [observed, temporal]:
    assert sha(parent / 'manifest.json') == report['parent_manifest_sha256']
    for name, digest in report['parent_files'].items():
        assert sha(parent / name) == digest, name
for folder, name, target, source in [
    ('plot1', 'upper_floor_and_counts.png', 'accel_upper_inventory_v1_diagnostics.png', 'observe1'),
    ('temporal_plot1', 'upper_temporal_all_controls.png', 'accel_upper_temporal_v1_diagnostics.png', 'temporal1')]:
    report = load(evidence / folder / 'report.json')
    assert report['input_report_sha256'] == sha(evidence / source / 'report.json')
    assert sha(evidence / folder / name) == report['image_sha256']
    shutil.copy2(evidence / folder / name, repo / 'research' / target)
    sources.add('research/' + target)
for folder, name, saved in [('audit1', 'tools/audit_accel_upper_inventory_v1.py', 'executed_auditor.py'),
                     ('known_check1', 'tools/check_accel_upper_known_v1.py', 'executed_check.py'),
                     ('temporal_audit1', 'tools/audit_accel_upper_temporal_v1.py', 'executed_auditor.py')]:
    assert sha(repo / name) == sha(evidence / folder / saved), name
    sources.add(name)
sources.update(['tools/plot_accel_upper_inventory_v1.py', 'tools/plot_accel_upper_temporal_v1.py',
    'tools/package_accel_upper_inventory_v1.py', 'research/加速高频漏提与颗粒V1.md',
    'AGENTS.md', 'handoff/研究续接.md', 'handoff/开发留痕.md'])
invariant = a.workspace / 'baselines/idle_microtexture_c_v1/inputs'
inputs = dict(parent_manifest=parent / 'manifest.json',
    data_workspace_AGENTS=a.workspace / 'AGENTS.md')
for filename, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
    data = load(invariant / filename)
    assert len(data) == count
    for name, digest in data.items():
        assert sha(repo / name) == digest, name
    inputs[filename] = invariant / filename
original_upper = sum(row['bands'][b]['counts']['old_accepted'] for row in observed['observations'] for b in range(2))
assert original_upper == 0
validation = dict(schema='vsl.accel-upper-inventory-freeze/1',
    result='all48_upper_census_and12_temporal_observations_audited_NO_sound_promotion',
    parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    audit=audit, known_waveform_audit=known, temporal_audit=temporal_audit,
    upper_candidates=[sum(row['bands'][b]['counts']['local_candidate'] for row in observed['observations']) for b in range(2)],
    original_upper_accepted=original_upper, local_floor_is_changed_observation_architecture=True,
    noise_and_numerical_tail_counterexamples_preserved=True, all_phase_controls_retained=True,
    unchanged_C_H=612, unchanged_old_voices=67, new_audio_or_profile=False, runtime_changed=False,
    plots_viewed=True, old61_driving_tests_repeated=False, source_identity_or_RPM_load_qualified=False,
    original_shared_phase_qualification_still_required=True, timbre_accepted=False,
    human_idle_priority='Existing F2 source-derived excitation and conditioned-detail pages await listening; no duplicate questions or blind promotion.',
    next='Upper persistent lines versus correlated non-Gaussian innovations and recording artifacts, before new acceleration recipe; no standalone OSC-cloud or threshold sweep.')
result = freeze(root, repo, sorted(sources), evidence, inputs, validation)
verify(root)
save(repo / 'research/accel_upper_inventory_v1_summary.json', dict(validation, **result))
append_index(repo / 'handoff/阶段索引.csv', ['accel_upper_inventory_v1',
    'baselines/accel_upper_inventory_v1/manifest.json', result['file_count'], result['manifest_sha256'],
    'All48 upper inventories/scalar rejections;12 known waves;12 temporal observations independently audited',
    'Changed band-local reference includes noise/numerical peaks;not sourceidentity or sound;612C-H67voices unchanged',
    'research/加速高频漏提与颗粒V1.md | research/accel_upper_inventory_v1_summary.json',
    'baselines/accel_upper_inventory_v1/validation.json'])
print(result)
