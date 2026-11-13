"""Retain both rejected exact budgets, independent proof and interrupted audit."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/idle_joint_budget_v1'
if a.stage=='verify':
    verify(root);print('Both rejected joint budgets and certificates verified.');raise SystemExit
evidence=a.workspace/'references/analysis/idle_joint_budget_v1'
observed=load(evidence/'observe1/report.json');cert=load(evidence/'certificate1/report.json')
audit=load(evidence/'audit2/report.json');plot=load(evidence/'plot1/report.json')
assert observed['result']=='both_joint_budget_families_examined_NO_sound_promotion'
assert cert['result']=='both_fixed_budget_separation_certificates_computed'
assert audit['result']=='both_budget_families_known_controls_tensor_maps_and_certificates_verified'
assert audit['real_families']==2 and audit['separation_certificates']==4
assert audit['known_inverse_controls']==6 and audit['known_ensembles']==2
assert audit['input_report_sha256']==cert['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert audit['certificate_report_sha256']==sha(evidence/'certificate1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit2/report.json')
for name,row in observed['families'].items():
    assert row['solution']['status']=='latent_indefinite_REJECTED' and row['solution']['rank']==10
    assert sha(evidence/'observe1'/(name+'_train.json'))==row['train_solution_sha256']
    assert cert['families'][name]['same_training_hyperplane_check_violates']
assert load(evidence/'audit1/interruption.json')['result']=='manually_interrupted_auditor_IO_bug'
assert (evidence/'audit1/executed_auditor.py').is_file()
assert sha(evidence/'plot1/idle_joint_budget_rejections.png')==plot['image_sha256']
shutil.copy2(evidence/'plot1/idle_joint_budget_rejections.png',repo/'research/idle_joint_budget_v1_diagnostics.png')
sources=set()
for name,digest in observed['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name)
    sources.add(name)
for folder,tool,saved in [('audit2','audit_idle_joint_budget_v1.py','executed_auditor.py'),
    ('certificate1','certify_idle_joint_budget_v1.py','executed_certificate.py'),
    ('plot1','plot_idle_joint_budget_v1.py','executed_plot.py')]:
    assert sha(repo/'tools'/tool)==sha(evidence/folder/saved)
    sources.add('tools/'+tool)
assert cert['plan_sha256']==sha(repo/'research/idle_joint_budget_certificate_v1_plan.json')==sha(evidence/'certificate1/executed_plan.json')
sources.update(['research/idle_joint_budget_certificate_v1_plan.json','tools/package_idle_joint_budget_v1.py',
    'research/怠速联合激励预算V1.md','research/idle_joint_budget_v1_diagnostics.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
parent=a.workspace/'baselines/idle_joint_cumulant_v1'
assert sha(parent/'manifest.json')==observed['parent_manifest_sha256']
table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
for name,digest in observed['inputs'].items():assert sha(parent/name)==digest==table[name]
inputs=dict(parent_manifest=parent/'manifest.json',data_workspace_AGENTS=a.workspace/'AGENTS.md')
for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name
    values=load(path);assert len(values)==count
    for source,digest in values.items():assert sha(repo/source)==digest,source
    inputs[name]=path
validation=dict(schema='vsl.idle-joint-budget-freeze/1',
    result='both_fixed_white_joint_budget_families_rejected_NO_sound_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    audit=audit,both_rank10_both_indefinite=True,training_only_solve=True,
    same_training_dual_violated_by_both_recording_portions=True,
    interrupted_auditor_and_exact_source_preserved=True,source_or_solver_not_rerun=True,plot_viewed=True,
    normalized10_required_change_lower_bounds={name:row['minimum_required_normalized10_moment_change'] for name,row in cert['families'].items()},
    lower_bound_NOT_nearest_model_or_statistical_uncertainty=True,
    no_event_rate_selected=True,new_audio_or_profile=False,runtime_changed=False,
    unchanged_C_H=612,unchanged_old_voices=67,old61_driving_tests_repeated=False,
    original_shared_phase_qualification_still_required=True,timbre_or_source_RPM_load_qualified=False,
    next='Observe source cross-band lag structure and effective response support with known/samePSD controls, before temporal joint law; no delay/rate/PSD-projection sweep. Existing hearing pending/no duplicate questions.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_joint_budget_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_joint_budget_v1','baselines/idle_joint_budget_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    'Both10x10 full tensor budgets;2exact ensembles/6inverse controls;independent SVD and4dual certificates',
    'Both fixed white positive-factor classes rejected for exact finite targets;not all joint laws;612C-H67voices unchanged',
    'research/怠速联合激励预算V1.md | research/idle_joint_budget_v1_summary.json',
    'baselines/idle_joint_budget_v1/validation.json'])
print(result)
