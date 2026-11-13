"""Freeze the actual failed prerequisite; withheld controls remain unexecuted."""
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
root=a.workspace/'baselines/phase_patch_v1'
if a.stage=='verify':
    verify(root)
    print('Failed phase-patch prerequisite freeze verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/phase_patch_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
diagnostic=load(evidence/'diagnose1/report.json')
da=load(evidence/'diagnostic_audit1/report.json')
plot=load(evidence/'plot1/report.json')
assert report['result']=='failed' and report['error']=='AssertionError()'
assert audit['result']=='failed_prerequisite_all12_native_inputs_fits_boundaries_and_original_gate_failure_verified'
assert diagnostic['result']=='all12_failed_control_raw_peaks_and_truth_conditioned_projections_recorded'
assert da['result']=='all12_raw_peak_arithmetic_and_truth_projection_omission_diagnostics_verified'
assert audit['windows']==12 and audit['lines']==117 and audit['withheld_cases_run'] is False
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==diagnostic['input_report_sha256']==da['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit1/report.json')==diagnostic['audit_report_sha256']
assert sha(evidence/'diagnose1/report.json')==da['diagnostic_report_sha256']==plot['diagnostic_report_sha256']
assert sha(evidence/'diagnostic_audit1/report.json')==plot['audit_report_sha256']
sources=set()
for folder in ['observe1','diagnose1']:
    for name,h in load(evidence/folder/'report.json')['sources'].items():
        assert sha(repo/name)==h==sha(evidence/folder/'exact_sources'/name)
        sources.add(name)
sources.update(v.relative_to(repo).as_posix() for v in (repo/'tools/native_phase_patch_v1').glob('*.py'))
sources.update(['tools/audit_phase_patch_v1.py','tools/audit_phase_patch_diagnostic_v1.py','tools/plot_phase_patch_v1.py',
    'tools/package_phase_patch_v1.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py',
    'research/连续相位曲率与漏峰V1.md','research/phase_patch_v1_omission.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
image=evidence/'plot1/omission.png'
assert sha(image)==plot['images']['omission.png']
shutil.copy2(image,repo/'research/phase_patch_v1_omission.png')
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'motion_controls_manifest.json':a.workspace/'baselines/chirp_motion_controls_v1/manifest.json'}
invariants=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    values=load(invariants/filename)
    assert len(values)==count
    for name,h in values.items():assert sha(repo/name)==h
    inputs[filename]=invariants/filename
validation=dict(schema='vsl.phase-patch-freeze/1',result='PREREQUISITE_FAILED_original_weak_peak_omission_verified_NO_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    planned_windows=108,executed_windows=12,withheld_windows=96,real_source_read=False,
    exact_executed_source_and_failure_retained=True,audit=audit,diagnostic_audit=da,
    omitted_component=dict(index=3,hz=115.7,windows=[9,10,11],prominence_db=[4.141,5.309,None],original_limit_db=8),
    posterior_truth_projection_NOT_estimation_or_initialization=True,new_boundary_noise_crossing_occlusion_qualified=False,
    actual_original_gate_failure_not_relaxed=True,no_threshold_degree_seed_budget_sweep=True,plot_viewed=True,
    new_audio_profile_C_or_runtime=False,C_H_unchanged=612,old_voices_unchanged=67,old61_tests_repeated=False,
    idle_pending_no_duplicate_question_or_blind_tune=True,original_common_phase_qualification_remains_required=True,
    next='Observed neighbouring-window candidate propagation with existence/absence joint tests and noise/nearline/occlusion controls; no truth slots, threshold relaxation or unconditional gap fill.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/phase_patch_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['phase_patch_v1','baselines/phase_patch_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'Cubic-rate-endpoint model/boundary rule;PREREQUISITE FAILED at window9;12native117lines/8970rawpeaks independently audited',
    '96windows withheld;no real source/newaudio/runtime/qualification;612C-H67voices unchanged',
    'research/连续相位曲率与漏峰V1.md | research/phase_patch_v1_summary.json','baselines/phase_patch_v1/validation.json'])
print(result)
