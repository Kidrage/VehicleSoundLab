"""Freeze the fully audited known-candidate experiment, including disqualification."""
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
root=a.workspace/'baselines/candidate_presence_v1'
if a.stage=='verify':
    verify(root)
    print('Known candidate propagation evidence and failed qualification freeze verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/candidate_presence_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
diag=load(evidence/'diagnose1/report.json')
da=load(evidence/'diagnostic_audit1/report.json')
plot=load(evidence/'plot2/report.json')
assert report['result']=='all108_known_candidate_presence_windows_complete'
assert audit['result']=='all108_native_augmented_waveforms_proposals_conditional_nulls_graphs_scores_verified'
assert diag['result']=='all108_native_augmented_and22_conditional_tests_postfit_diagnostics_recorded'
assert da['result']=='all_postfit_forecasts_native_augmented_and_conditional_diagnostics_verified'
assert report['executed_windows']==audit['windows']==108 and report['prerequisite_passed']
assert audit['native_lines']==924 and audit['raw_lines']==946 and audit['conditional_tests']==22
assert audit['qualified'] is False and audit['qualification']['am_fm_all6low_atleast5'] is False
assert all(v for k,v in audit['qualification'].items() if k!='am_fm_all6low_atleast5')
assert da['cases']==9 and da['forecasts']==749 and da['conditional_tests']==22
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==diag['input_report_sha256']==da['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit1/report.json')==diag['audit_report_sha256']==da['audit_report_sha256']==plot['audit_report_sha256']
assert sha(evidence/'diagnose1/report.json')==da['diagnostic_report_sha256']==plot['diagnostic_report_sha256']
assert sum(v['accepted'] for v in diag['all_conditional_tests'])==4
sources=set()
for folder in ['observe1','diagnose1']:
    for name,h in load(evidence/folder/'report.json')['sources'].items():
        assert sha(repo/name)==h==sha(evidence/folder/'exact_sources'/name)
        sources.add(name)
sources.update(v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1']
    for v in (repo/'tools'/directory).glob('*.py'))
sources.update(['tools/audit_candidate_presence_v1.py','tools/audit_candidate_presence_diagnostic_v1.py',
    'tools/plot_candidate_presence_v1.py','tools/package_candidate_presence_v1.py',
    'tools/chirp_motion_controls_v1/audit_inputs.py','tools/native_chirp_audit_v1/wave.py',
    'tools/native_chirp_audit_v1/temporal.py','research/观察候选与存在检验V1.md',
    'research/candidate_presence_v1_comparison.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
image=evidence/'plot2/comparison.png'
assert sha(image)==plot['images']['comparison.png']
shutil.copy2(image,repo/'research/candidate_presence_v1_comparison.png')
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'phase_patch_manifest.json':a.workspace/'baselines/phase_patch_v1/manifest.json',
    'motion_controls_manifest.json':a.workspace/'baselines/chirp_motion_controls_v1/manifest.json',
    'pending_idle_manifest.json':a.workspace/'baselines/idle_conditioned_detail_v1/manifest.json'}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename
    table=load(path)
    assert len(table)==count
    for name,h in table.items():assert sha(repo/name)==h
    inputs[filename]=path
validation=dict(schema='vsl.candidate-presence-freeze/1',
    result='exact_weak_line_prerequisite_repaired_FULL_QUALIFICATION_FAILED_no_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    known_windows=108,native_lines=924,raw_augmented_lines=946,conditional_tests=22,accepted_added=4,
    input_and_failure_and_raw_accepted_exact_sources_retained=True,audit=audit,diagnostic_audit=da,
    original_local_boxes_tolerance_and60evaluations_per_hypothesis=True,worst_case120evaluations_per_window=True,
    native_hypothesis_not_silently_selected_on_augmented_failure=True,
    fully_nonlinear_absent_optimum_or_statistical_confidence=False,
    truth_only_postfit_diagnostic=True,plots_viewed=True,first_plot_note_overlap_retained_second_layout_only=True,
    C_H_unchanged=612,old_voices_unchanged=67,real_source_read=False,new_audio_profile_or_runtime=False,
    old61_driving_tests_repeated=False,idle_pending_no_duplicate_blind_tune_or_promotion=True,
    original_common_phase_qualification_remains_required=True,
    next='Before adding a candidate, distinguish already detected current lines from inaccurate extrapolation using current-wave/residual evidence; declare new method and repeat all known controls without threshold/degree/budget sweeps.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/candidate_presence_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['candidate_presence_v1','baselines/candidate_presence_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '108known windows;924native+946augmented lines;22conditional tests;749forecasts independently audited;weak-line prerequisite repaired',
    'Full qualification FAILED:AMFM4newoptimizerfailures;no real source/newaudio/runtime;612C-H67voices unchanged',
    'research/观察候选与存在检验V1.md | research/candidate_presence_v1_summary.json','baselines/candidate_presence_v1/validation.json'])
print(result)
