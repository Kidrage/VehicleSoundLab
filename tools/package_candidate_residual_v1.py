"""Freeze the original residual-screen false negative without relaxing its gate."""
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
root=a.workspace/'baselines/candidate_residual_v1'
if a.stage=='verify':
    verify(root)
    print('Original residual-screen false negative and evidence freeze verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/candidate_residual_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
diag=load(evidence/'diagnose1/report.json')
plot=load(evidence/'plot1/report.json')
assert report['result']=='failed' and report['error']=="AssertionError('Original exact-cubic prerequisite failed')"
assert report['executed_windows']==audit['windows']==12 and report['prerequisite_passed'] is False
assert audit['result']=='all12_prerequisite_screen_false_negative_inputs_raw_accepted_nulls_graphs_scores_verified'
assert diag['result']=='all12_fixed_native_screen_and_frozen_joint_models_independently_reconstructed'
assert audit['native_lines']==117 and audit['raw_lines']==119 and audit['screen_tests']==3 and audit['postfit_tests']==2
assert audit['remaining96_executed'] is False and audit['qualified'] is False
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==diag['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit1/report.json')==diag['audit_report_sha256']==plot['audit_report_sha256']
assert sha(evidence/'diagnose1/report.json')==plot['diagnostic_report_sha256']
assert [v['passed'] for v in audit['screen_gains']]==[True,True,False]
assert abs(min(audit['screen_gains'][-1]['gain_LR'])-.792532431602878)<1e-12
sources=set()
for folder in ['observe1','diagnose1']:
    for name,h in load(evidence/folder/'report.json')['sources'].items():
        assert sha(repo/name)==h==sha(evidence/folder/'exact_sources'/name)
        sources.add(name)
sources.update(v.relative_to(repo).as_posix() for directory in ['candidate_residual_v1','candidate_presence_v1','native_phase_patch_v1']
    for v in (repo/'tools'/directory).glob('*.py'))
sources.update(['tools/audit_candidate_residual_v1.py','tools/plot_candidate_residual_v1.py',
    'tools/package_candidate_residual_v1.py','tools/native_chirp_audit_v1/wave.py',
    'tools/native_chirp_audit_v1/temporal.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'research/候选残差预筛选V1.md','research/candidate_residual_v1_false_negative.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
image=evidence/'plot1/false_negative.png'
assert sha(image)==plot['images']['false_negative.png']
shutil.copy2(image,repo/'research/candidate_residual_v1_false_negative.png')
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'candidate_presence_manifest.json':a.workspace/'baselines/candidate_presence_v1/manifest.json',
    'known_source_signal_report.json':a.workspace/'baselines/chirp_motion_controls_v1/evidence/observe1/report.json',
    'pending_idle_manifest.json':a.workspace/'baselines/idle_conditioned_detail_v1/manifest.json'}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename
    values=load(path)
    assert len(values)==count
    for name,h in values.items():assert sha(repo/name)==h
    inputs[filename]=path
validation=dict(schema='vsl.candidate-residual-freeze/1',
    result='PREREQUISITE_FAILED_true_weak_line_false_negative_fixed_native_basis_no_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    planned_windows=108,executed_windows=12,remaining_windows_not_executed=96,
    audit=audit,independent_model_diagnostic=diag,
    original_failure_threshold_and_exact_sources_preserved=True,threshold_budget_degree_seed_window_sweep=False,
    new_acceptance_is_fixed_nonlinear_global_conditional_linear_gain=True,
    statistical_confidence_or_nonlinear_absent_optimum=False,
    old_joint_model_used_only_as_diagnostic_not_hidden_fallback=True,plot_viewed=True,
    C_H_unchanged=612,old_voices_unchanged=67,real_source_read=False,new_audio_profile_or_runtime=False,
    old61_driving_tests_repeated=False,idle_pending_no_duplicate_blind_tune_or_promotion=True,
    original_common_phase_qualification_remains_required=True,
    next='Declare full present/absent model comparison and independent prediction, preserve optimizer failures as unknown rather than absence; no threshold relaxation or hidden fallback.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/candidate_residual_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['candidate_residual_v1','baselines/candidate_residual_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '12known windows117native+119fit lines;3preinsertion2postfit nulls/allgraphs/scores audited;fixed-vs-joint models independently reconstructed',
    'PREREQUISITE FAILED:window11 true115.7Hz gain.79253 rejected;96withheld;noaudio/runtime;612C-H67voices unchanged',
    'research/候选残差预筛选V1.md | research/candidate_residual_v1_summary.json','baselines/candidate_residual_v1/validation.json'])
print(result)
