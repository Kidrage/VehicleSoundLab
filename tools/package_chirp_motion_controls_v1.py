"""Freeze all fixed AM/FM/noise controls and independent verification."""
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
root=a.workspace/'baselines/chirp_motion_controls_v1'
if a.stage=='verify':
    verify(root)
    print('Motion mechanism freeze verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/chirp_motion_controls_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
plot=load(evidence/'plot1/report.json')
assert report['result']=='all60_native_AM_FM_mono_noise_mechanism_controls_complete'
assert audit['result']=='all60_known_native_signals_inventories_observed_initials_fits_truth_connections_verified'
assert audit['windows']==60 and audit['lines']==548 and report['real_source_read'] is False
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit1/report.json')==plot['audit_report_sha256']
for name,h in report['sources'].items():
    assert sha(repo/name)==h==sha(evidence/'observe1/exact_sources'/name)
image=evidence/'plot1/mechanisms.png'
assert sha(image)==plot['images']['mechanisms.png']
shutil.copy2(image,repo/'research/chirp_motion_controls_v1_mechanisms.png')
sources=list(report['sources'])+['tools/chirp_motion_controls_v1/audit_inputs.py',
    'tools/audit_chirp_motion_controls_v1.py','tools/native_chirp_audit_v1/wave.py',
    'tools/native_chirp_audit_v1/temporal.py','tools/plot_chirp_motion_controls_v1.py',
    'tools/package_chirp_motion_controls_v1.py','research/低频断线机制V1.md',
    'research/chirp_motion_controls_v1_mechanisms.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'previous_profiled_manifest.json':a.workspace/'baselines/accel_low_profiled_v1/manifest.json'}
invariants=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    table=load(invariants/filename)
    assert len(table)==count
    for name,h in table.items():assert sha(repo/name)==h
    inputs[filename]=invariants/filename
validation=dict(schema='vsl.chirp-motion-controls-freeze/1',
    result='current_native_path_linear_connection_false_breaks_and_local_noise_support_verified',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    cases=report['summaries'],true_components=audit['true_components'],independent_audit=audit,
    all5_predeclared_cases_retained=True,truth_never_used_for_initialization=True,
    original_model_bounds_budget_gates_and_linker_unchanged=True,plot_viewed=True,
    noise_capacity_rejection=False,noise_is_not_an_engine_or_source_classifier=True,
    real_source_read=False,new_audio_profile_or_runtime=False,C_H_unchanged=612,old_voices_unchanged=67,
    old61_tests_repeated=False,idle_listening_pending_no_duplicate_question_or_blind_tune=True,
    original_common_phase_qualification_remains_required=True,
    next='Known-control qualification of local continuous phase curvature and noise-constrained cross-window correspondence; preserve original rules, no threshold/budget sweeps, then declared source case.')
result=freeze(root,repo,sources,evidence,inputs,validation)
verify(root)
save(repo/'research/chirp_motion_controls_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['chirp_motion_controls_v1','baselines/chirp_motion_controls_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'All60native known AM/FM/mono-noise windows;548lines;exact-trajectory false breaks and9noise local supports;independent audit',
    'No real-source/RPM/commonphase qualification or newaudio;612C-H67voices unchanged;idle listening pending',
    'research/低频断线机制V1.md | research/chirp_motion_controls_v1_summary.json','baselines/chirp_motion_controls_v1/validation.json'])
print(result)
