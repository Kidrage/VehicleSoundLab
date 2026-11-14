"""Freeze rejected source conditional-mean evidence without promoting a voice."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_conditional_gain_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_conditional_gain_v1'
failed=load(evidence/'run1/report.json');run=load(evidence/'run2/report.json')
diag=load(evidence/'diagnosis1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert failed['result']=='failed' and 'row_stack' in failed['error']
assert run['result']=='native_conditional_mean_fitted_pending_audit' and not run['source_conditional_mean_available']
assert run['known']['conditional']['available'] and run['known']['parameter_error']<1e-5
assert run['models']['source']['conditional']['success'] and run['models']['source']['conditional']['active_mask'].count(-1)==3
assert diag['result']=='rejected_source_fixed_diagnosis' and not diag['refit'] and not diag['bounds_or_parameters_changed']
assert diag['input_sha256']==sha(evidence/'run2/report.json')
assert audit['result']=='passed' and audit['QR_factorizations']==1624 and len(audit['cases'])==14
assert audit['input_sha256']==sha(evidence/'run2/report.json') and audit['diagnosis_sha256']==sha(evidence/'diagnosis1/report.json')
assert assessment['result']=='rejected_source_conditional_mean_assessed' and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert assessment['input_sha256']==sha(evidence/'run2/report.json') and assessment['diagnosis_sha256']==sha(evidence/'diagnosis1/report.json')
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'run2/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for row in [run['known']['training_arrays']]+run['known']['predictions']+run['evaluations']:
    assert sha(evidence/'run2'/row['file'])==row['sha256']
for row in diag['cases']:
    assert sha(evidence/'diagnosis1'/row['file'])==row['sha256'] and sha(row['original_file'])==row['original_sha256']
for path,folder,name in [('tools/diagnose_idle_conditional_gain_v1.py','diagnosis1','executed_diagnosis.py'),
    ('tools/audit_idle_conditional_gain_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_idle_conditional_gain_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
plan='research/idle_conditional_gain_v1_diagnosis_plan.json'
assert sha(repo/plan)==diag['plan_sha256']==sha(evidence/'diagnosis1'/Path(plan).name);sources.add(plan)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle_conditional_gain_v1.png');sources.add('research/idle_conditional_gain_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_conditional_gain_v1.py','research/怠速条件力度前向拟合V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_known_forward_manifest.json':a.workspace/'baselines/joint_osc_forward_v1/manifest.json',
    'previous_source_relation_manifest.json':a.workspace/'baselines/idle_amp_phase_link_v1/manifest.json',
    'source_partition_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.idle-conditional-gain-freeze/1',result='source_conditional_mean_REJECTED_not_new_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='6e0643f qualified and froze known joint OSC forward/inverse/power; clean verified before source inverse work',
    original_NumPy_row_stack_API_failure_preserved=True,repair_only_vstack_no_model_or_gate_change=True,
    known10parameter_error=run['known']['parameter_error'],known_Jacobian_condition=run['known']['conditional']['condition'],
    all4TRAIN_models_frozen_before_CHECK=True,source_conditional_available=False,source_active_slopes=3,
    source_CHECK_fixed_diagnosis_only=True,source_CHECK_complex_MSE_reduction=assessment['source_CHECK_complex_MSE_reduction'],
    source_CHECK_complex_error_variance_reduction=assessment['source_CHECK_complex_error_variance_reduction'],
    independent_QR_factorizations=1624,all14portions_native_gains_mean_waves_and_window_coefficients_checked=True,
    maximum_independent_QR_coefficient_error_FS=audit['errors']['all_QR_coefficients'],
    maximum_mean_waveform_error_FS=audit['errors']['all_mean_waveforms'],all_trace_costs_and_residual_signed_covariances_checked=True,
    hidden_innovation_mean_identity_only_NOT_variance_or_likelihood=True,complete_source_joint_model_identified=False,
    figure_viewed=True,new_source_voice_or_audition=False,listening_improvement_claimed=False,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,
    next='Source residual innovation variance/time structure through same forward observer with main/residual power. Do not widen bound or synthesize a mean-only voice;187counterexample independent. Pending idle audition before C; original phase qualifications/full driving/multi-engine/7.1.4 goal active.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_conditional_gain_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_conditional_gain_v1','baselines/idle_conditional_gain_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '4TRAIN2+10param;source3bounds;fixedCHECK;14portions1624QR',
    'REJECTEDsource;conditionalMEANnotlatentvariance;619C-H67voicesexact;noC/listening',
    'research/怠速条件力度前向拟合V1.md | research/idle_conditional_gain_v1_summary.json','baselines/idle_conditional_gain_v1/validation.json'])
print(result)
