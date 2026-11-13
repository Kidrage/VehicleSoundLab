"""Freeze every joint idle observation and invariant, without audio promotion."""
import argparse, shutil, subprocess
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, verify, append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/idle_joint_cumulant_v1'
if a.stage=='verify':
    verify(root)
    print('Joint idle cumulant archive verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/idle_joint_cumulant_v1'
observed=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
plot=load(evidence/'plot2/report.json')
assert observed['result']=='all_joint_idle_observations_complete_NO_sound_promotion'
assert audit['result']=='all57_joint_observations_and_independent_architecture_verified'
assert audit['observations']==57 and audit['matrices']==114 and audit['exact_known_ensembles']==3
assert audit['all6_pair_summaries_verified'] and len(observed['pairs'])==6
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit1/report.json')
assert plot['generated_blocks']==48 and plot['phase_controls']==6
assert sha(evidence/'plot2/idle_joint_all_pairs.png')==plot['image_sha256']
shutil.copy2(evidence/'plot2/idle_joint_all_pairs.png',repo/'research/idle_joint_cumulant_v1_diagnostics.png')
sources=set()
for name,digest in observed['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
    sources.add(name)
assert sha(repo/'tools/audit_idle_joint_cumulant_v1.py')==sha(evidence/'audit1/executed_auditor.py')
assert sha(repo/'tools/plot_idle_joint_cumulant_v1.py')==sha(evidence/'plot2/executed_plot.py')
sources.update(['tools/audit_idle_joint_cumulant_v1.py','tools/plot_idle_joint_cumulant_v1.py',
    'tools/package_idle_joint_cumulant_v1.py','research/怠速跨频带颗粒V1.md',
    'research/idle_joint_cumulant_v1_diagnostics.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs={'data_workspace_AGENTS':a.workspace/'AGENTS.md'}
tables={}
for name,digest in observed['parent_manifests'].items():
    path=a.workspace/'baselines'/name/'manifest.json'
    assert sha(path)==digest
    tables[name]={v['path']:v['sha256'] for v in load(path)['files']}
    inputs[name+'_manifest.json']=path
for path,digest in observed['inputs'].items():
    path=Path(path)
    relative=path.relative_to(a.workspace/'baselines')
    assert sha(path)==digest==tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name
    values=load(path)
    assert len(values)==count
    for source,digest in values.items():
        assert sha(repo/source)==digest,source
    inputs[name]=path
above_all_generated=all(
    min(row[transform]['normalized'][b][c] for row in observed['observations'] if row['kind']=='source') >
    max(row[transform]['normalized'][b][c] for row in observed['observations'] if row['kind'] in ['sparse','conditioned50'])
    for b,c in [row['bands'] for row in observed['pairs']] for transform in ['raw','local40ms'])
assert above_all_generated
validation=dict(schema='vsl.idle-joint-cumulant-freeze/1',
    result='all57_joint_observations_audited_NOT_sound_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    audit=audit,all6pairs_both_raw_above_controls_and_independent_full=all(v['both_raw_above_controls_and_full_expectation'] for v in observed['pairs']),
    all6pairs_both_local40ms_above_phase_controls=all(all(x['exceeds_every_phase_control'] for x in v['local40ms']) for v in observed['pairs']),
    all6pairs_both_raw_and_local40ms_above_all48generated=above_all_generated,
    source_portions=2,phase_controls=6,all_generated_blocks=48,plots_viewed=True,
    source_identity_or_RPM_load_qualified=False,timbre_accepted=False,new_audio_or_profile=False,
    runtime_changed=False,unchanged_C_H=612,unchanged_old_voices=67,
    old61_driving_tests_repeated=False,original_shared_phase_qualification_still_required=True,
    next='Joint-innovation feasibility with complete marginal/cross/filter budgets and known counterexamples; preserve pending listening, no duplicate questions or blind C adoption.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/idle_joint_cumulant_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_joint_cumulant_v1','baselines/idle_joint_cumulant_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '57observations/114joint matrices;3exact ensembles;independent FFT/scalar/FIR budgets;all48generated blocks',
    'Same-recording joint concentration not mechanical identity/significance/sound promotion;612C-H67voices unchanged',
    'research/怠速跨频带颗粒V1.md | research/idle_joint_cumulant_v1_summary.json',
    'baselines/idle_joint_cumulant_v1/validation.json'])
print(result)
