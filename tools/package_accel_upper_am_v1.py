"""Freeze complete persistent joint-gain source fits and known/native independent verification."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/accel_upper_am_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_am_v1'
run=load(evidence/'fit1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_joint_positive_gain_fits_terminal' and len(run['observations'])==12
assert audit['result']=='passed' and audit['cases']==12 and audit['trace_evaluations']==437 and audit['source_available']==3
assert assessment['result']=='all12_joint_gain_fits_assessed_not_voice' and len(assessment['cases'])==12
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'fit1/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit1/report.json')
assert run['known']['known_recovery_error']<1e-6 and run['known']['known_fit']['available']
assert sha(evidence/'fit1/known.npz')==run['known_arrays_sha256']
sources=set(run['sources'])
for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(evidence/'fit1/exact_sources'/path)
parent=a.workspace/'baselines/accel_upper_forward_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
for path,digest in run['parent_files'].items():assert sha(parent/path)==digest==table[path]
trace_count=len(run['known']['known_fit']['trace']);original_count=control_count=0
for row,item in zip(run['observations'],assessment['cases']):
    assert sha(evidence/'fit1'/row['file'])==row['sha256'];fit=row['fit'];trace_count+=len(fit['trace'])
    assert item['segment']==row['segment'] and item['branch']==row['branch'] and item['Gamma']==row['Gamma']
    for key in ['available','success','status','nfev','rank','condition','bound_mask']:assert item[key]==fit[key]
    assert item['tau_ms']==1000*row['tau_seconds'] and item['initial_cost']==fit['initial_cost'] and item['final_cost']==fit['cost']
    assert item['cost_reduction_from_initial']==1-fit['cost']/fit['initial_cost'] and item['maximum_error']==row['maximum_error']
    if row['branch']=='original':assert fit['available'];original_count+=1
    else:assert not fit['available'] and fit['bound_mask'][-1];control_count+=1
assert trace_count==437 and original_count==assessment['source_available']==3 and control_count==9 and assessment['control_available']==0
for path,folder,name in [('tools/audit_accel_upper_am_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_upper_am_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
for fig in assessment['figures']:
    path=evidence/'assessment1'/fig['file'];assert sha(path)==fig['sha256']
    name='research/accel_upper_am_v1_'+fig['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_accel_upper_am_v1.py','research/高频联合持续起伏V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs=dict(parent_manifest=parent/'manifest.json',idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json',
            C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voices_path,
            prior_link_manifest=a.workspace/'baselines/accel_upper_link_v1/manifest.json')
validation=dict(schema='vsl.accel-upper-am-freeze/1',result='native_joint_positive_gain_forward_inverse_and12fits_verified_NOT_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='0e9b7db native second/fourth forward operator and full source iid-shape failure, independent audits and archive; clean verified, not a wait-only turn',
    known11inverse_before_source=True,known_result=run['known'],all12_source_and_phase_cases=True,
    all437evaluation_costs=True,all_known_and_terminal_Jacobians=True,independent_audit=audit,
    three_real_numeric_available=True,nine_phase_controls_bound_unavailable=True,bounds_and_initial_and_max60_unchanged=True,
    all_assessment_rows_verified=True,figures_viewed=True,post_carrier_filter_gain=True,
    source_carrier_PSD_or_LRCSD_fitted=False,post_gain_refiltered_mix_budget_qualified=False,
    four_recording_coordinates_not_physical_sources=True,not_independent_holdout_or_confidence_intervals=True,
    numeric_availability_not_timbre_acceptance=True,new_listening_audio=False,new_runtime_profile=False,new_C=False,
    new_download=False,old_CTests_repeated=False,old619C_H_and67voices_exact=True,
    moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    full_MSC_original_gate_still_unpassed=True,original_common_phase_qualification_unwaived=True,
    next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_am_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_am_v1','baselines/accel_upper_am_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'full4x4OU-nativeW;known11inverse;12fits437traceAllJ;8sKnownNative',
    '3realNumericOnly9controlsBound;postfilterSides/PSDpending;619C-H67voices',
    'research/高频联合持续起伏V1.md | research/accel_upper_am_v1_summary.json','baselines/accel_upper_am_v1/validation.json'])
print(result)
