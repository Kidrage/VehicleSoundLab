"""Freeze known-control adoption/prediction evidence including all unresolved fits."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/candidate_prediction_v1'
if a.stage=='verify':
    verify(root)
    print('All known candidate prediction evidence and unresolved failures verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/candidate_prediction_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit2/report.json')
failed=load(evidence/'audit1/report.json')
plot=load(evidence/'plot1/report.json')
assert report['result']=='all108_known_full_candidate_prediction_windows_complete'
assert audit['result']=='all108_full_masked_predictions_adoption_graphs_and_scores_independently_verified'
assert failed['result']=='failed' and failed['error'].startswith('TypeError(')
assert audit['windows']==108 and audit['native_lines']==924 and audit['raw_lines']==950 and audit['selected_lines']==928
assert audit['verification_fits']==46 and audit['verification_lines']==428 and audit['prediction_tests']==26
assert audit['prediction_supported']==4 and audit['prediction_unknown']==10 and audit['adopted_windows']==4
assert audit['qualified_known_controls'] and all(audit['qualification'].values())
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit2/report.json')==plot['audit_report_sha256']
sources=set()
for name,h in report['sources'].items():
    assert sha(repo/name)==h==sha(evidence/'observe1/exact_sources'/name)
    sources.add(name)
sources.update(v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
    for v in (repo/'tools'/directory).glob('*.py'))
sources.update(['tools/audit_candidate_prediction_v1.py','tools/plot_candidate_prediction_v1.py','tools/package_candidate_prediction_v1.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'research/完整模型与保留数据预测V1.md','research/candidate_prediction_v1_known.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
image=evidence/'plot1/known_comparison.png'
assert sha(image)==plot['images']['known_comparison.png']
shutil.copy2(image,repo/'research/candidate_prediction_v1_known.png')
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'candidate_presence_manifest.json':a.workspace/'baselines/candidate_presence_v1/manifest.json',
    'known_signal_report.json':a.workspace/'baselines/chirp_motion_controls_v1/evidence/observe1/report.json',
    'pending_idle_manifest.json':a.workspace/'baselines/idle_conditioned_detail_v1/manifest.json'}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename
    values=load(path)
    assert len(values)==count
    for name,h in values.items():assert sha(repo/name)==h
    inputs[filename]=path
validation=dict(schema='vsl.candidate-prediction-freeze/1',result='KNOWN_controls_pass_conditional_prediction_explicit_adoption_NOT_real_source_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),audit=audit,
    all_failed_augmented_and_verification_attempts_retained=True,
    prior_selection_rule_explicitly_replaced_not_hidden_fallback=True,native_preservation_not_candidate_absence=True,
    whole_window_and_neighbor_conditioned_not_pristine_holdout=True,
    check_parameters_never_refitted=True,unknown_solver_failures_not_absence=True,
    original60_per_hypothesis_not_same_total_compute=True,first_boolean_audit_failure_preserved=True,plot_viewed=True,
    C_H_unchanged=612,old_voices_unchanged=67,real_source_read=False,new_audio_profile_or_runtime=False,
    old61_driving_tests_repeated=False,idle_pending_no_duplicate_blind_tune_or_promotion=True,
    original_common_phase_qualification_remains_required=True,
    next='Declare and execute all original48 F3 native windows with cubic native and the same full-hypothesis verification/adoption, retaining all failures and perspectives before any profile/audio.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/candidate_prediction_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['candidate_prediction_v1','baselines/candidate_prediction_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '108known/924native950attempt928selected lines;46masked428lines/26prediction tests independently audited;declared criteria pass',
    '4supported10unknown12unsupported;explicit native-preserving adoption;conditioned not pristine;no realdata/audio/runtime;612C-H67voices unchanged',
    'research/完整模型与保留数据预测V1.md | research/candidate_prediction_v1_summary.json','baselines/candidate_prediction_v1/validation.json'])
print(result)
