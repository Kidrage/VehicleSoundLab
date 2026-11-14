"""Freeze failed known clock inverse and numerical seam diagnosis, no voice adoption."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle75_clock_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle75_clock_v1'
first=load(evidence/'fit1/report.json');run=load(evidence/'fit2/report.json')
diag=load(evidence/'derivative_diagnosis1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert first['result']=='failed' and not first['models']
assert run['result']=='failed' and not run['models'] and not run['CHECK']
assert diag['result']=='cubic_node_seam_truncation_identified' and diag['gate']==1e-6 and diag['step']==1e-6
assert diag['original_report_sha256']==sha(evidence/'fit1/report.json')
assert run['known']['inverse']['available'] and run['known']['parameter_error']>1e-5
assert audit['result']=='failed_known_inverse_independently_confirmed' and audit['QR_factorizations']==348
assert audit['input_sha256']==sha(evidence/'fit2/report.json') and audit['analytic_derivative_and_forward_response_consistent']
assert len(audit['profile'])==21 and not audit['new_source_fit'] and not audit['new_audio']
assert assessment['result']=='failed_known_idle75_clock_assessed' and assessment['source_models_fitted']==0
assert assessment['input_sha256']==sha(evidence/'fit2/report.json') and assessment['audit_sha256']==sha(evidence/'audit1/report.json')
sources=set()
for path,digest in run['sources'].items():
    assert sha(repo/path)==digest==sha(evidence/'fit2/exact_sources'/path);sources.add(path)
for path,digest in run['inputs'].items():assert sha(path)==digest
for row in run['streams']:assert sha(evidence/'fit2'/row['file'])==row['sha256']
for path,folder,name in [('tools/diagnose_idle75_clock_derivative_v1.py','derivative_diagnosis1','executed_diagnosis.py'),
    ('tools/audit_idle75_clock_v1.py','audit1','executed_auditor.py'),('tools/assess_idle75_clock_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
for path,folder,digest in [('research/idle75_clock_v1_derivative_diagnosis.json','derivative_diagnosis1',diag['plan_sha256']),
    ('research/idle75_clock_v1_inverse_diagnosis.json','audit1',audit['plan_sha256'])]:
    assert sha(repo/path)==digest==sha(evidence/folder/Path(path).name);sources.add(path)
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle75_clock_v1.png');sources.add('research/idle75_clock_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle75_clock_v1.py','research/怠速75Hz速度拟合核查V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'previous_variation_manifest.json':a.workspace/'baselines/idle_variation_budget_v1/manifest.json',
    'actual_audio_manifest.json':a.workspace/'baselines/idle_local_partition_v1/manifest.json',
    'old_AM_manifest.json':a.workspace/'baselines/idle_phase_amplitude_v1/manifest.json',
    'C_H_index.csv':repo/'handoff/C文件索引.csv','original_voice_hashes.json':voices_path}
validation=dict(schema='vsl.idle75-clock-freeze/1',result='known_inverse_FAILED_NO_source_fit_or_audio',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='1ecfee4 actual153case layer budget identified75slow/187detail and phase-estimator confound; clean verified',
    source_derived64tap3input_row_arbitrary_clock_marginal_variance_checked=True,
    native_positive_gain_E_square_one_NOT_take_RMS=True,independent75_missing_old_cross_coupling_explicit=True,
    original_central_difference_seam_failure_preserved=True,diagnosis_same_step_same_gate=True,
    independent348QR_all_native_nodes_trace_moments_costs_Jacobian_checked=True,
    independent_known_returned_parameters=audit['known_returned_parameters'],known_truth=audit['known_truth'],
    known_maximum_parameter_error=audit['known_parameter_error'],known_returned_cost=audit['returned_scaled_cost'],known_truth_cost=audit['truth_scaled_cost'],
    optimizer_success_NOT_method_qualification=True,original_known_recovery_gate_NOT_relaxed=True,
    all21fixed_line_diagnostic_points_preserved=True,no_new_start_bounds_seeds_iterations=True,
    source_models_fitted=0,new_audio=False,figure_viewed=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,listening_improvement_claimed=False,
    next=assessment['next']+' Preserve phase estimator in source-forward comparison,187detail separate, pending idle hearing/original phase qualifications/full driving/multi-engine/7.1.4 goal active.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle75_clock_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle75_clock_v1','baselines/idle75_clock_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'KNOWNinverseFAIL(.279);3seed3s;348QR;21fixedline;C1derivativefix',
    'solverSuccessNOTknownRecovery;NOsourcefit/audio;619C-H67voicesexact',
    'research/怠速75Hz速度拟合核查V1.md | research/idle75_clock_v1_summary.json','baselines/idle75_clock_v1/validation.json'])
print(result)
