"""Freeze all original F3 observations, unresolved hypotheses and independent audit."""
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
root=a.workspace/'baselines/accel_candidate_prediction_v1'
if a.stage=='verify':
    verify(root)
    print('All48 real-source candidate prediction evidence freeze verified.')
    raise SystemExit
evidence=a.workspace/'references/analysis/accel_candidate_prediction_v1'
report=load(evidence/'observe1/report.json')
audit=load(evidence/'audit1/report.json')
plot=load(evidence/'plot1/report.json')
assert report['result']=='all48_original_F3_cubic_candidate_prediction_observations_complete'
assert audit['result']=='all48_F3_native_augmented_masked_predictions_adoption_graphs_verified'
assert report['native_windows_completed']==report['selected_windows_completed']==audit['windows']==48
assert report['real_source_read'] and report['new_audio_or_profile'] is False
assert audit['observations']==report['observations']
assert sha(evidence/'observe1/report.json')==audit['input_report_sha256']==plot['input_report_sha256']
assert sha(evidence/'audit1/report.json')==plot['audit_report_sha256']
assert audit['prediction_tests']==plot['prediction_tests']
sources=set()
for name,h in report['sources'].items():
    assert sha(repo/name)==h==sha(evidence/'observe1/exact_sources'/name)
    sources.add(name)
sources.update(v.relative_to(repo).as_posix() for directory in ['native_phase_patch_v1','candidate_presence_v1','candidate_prediction_v1']
    for v in (repo/'tools'/directory).glob('*.py'))
sources.update(['tools/audit_accel_candidate_prediction_v1.py','tools/plot_accel_candidate_prediction_v1.py',
    'tools/accel_candidate_prediction_v1/coverage.py','research/accel_candidate_prediction_v1_coverage_plan.json',
    'tools/package_accel_candidate_prediction_v1.py','tools/native_chirp_audit_v1/wave.py',
    'tools/native_chirp_audit_v1/temporal.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'research/F3完整模型与预测V1.md','research/accel_candidate_prediction_v1_tracks.png',
    'research/accel_candidate_prediction_v1_predictions.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
for original,destination in [('source_status_tracks.png','accel_candidate_prediction_v1_tracks.png'),
    ('source_predictions.png','accel_candidate_prediction_v1_predictions.png')]:
    image=evidence/'plot1'/original
    assert sha(image)==plot['images'][original]
    shutil.copy2(image,repo/'research'/destination)
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'known_qualification_manifest.json':a.workspace/'baselines/candidate_prediction_v1/manifest.json',
    'old_full_fit_manifest.json':a.workspace/'baselines/accel_low_fit_v1/manifest.json',
    'old_profiled_manifest.json':a.workspace/'baselines/accel_low_profiled_v1/manifest.json',
    'pending_idle_manifest.json':a.workspace/'baselines/idle_conditioned_detail_v1/manifest.json'}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename
    values=load(path)
    assert len(values)==count
    for name,h in values.items():assert sha(repo/name)==h
    inputs[filename]=path
continuous=sum(v['variants']['selected_boundary']['low_start_tracks_atleast5'] for v in report['observations'])
validation=dict(schema='vsl.accel-candidate-prediction-freeze/1',
    result='all48_F3_observations_audited_NO_source_identity_or_audio_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    audit=audit,selected_low_start_tracks_atleast5=continuous,
    all_native_full_masked_deleted_unknown_attempts_retained=True,no_subset_ranking_or_budget_sweep=True,
    same_qualified_algorithm_sources=True,workers4_and_BLAS2_NOT_realtime_performance_claim=True,
    whole_window_neighbor_conditioned_not_pristine_holdout=True,unknown_not_absence=True,
    plots_viewed=True,C_H_unchanged=612,old_voices_unchanged=67,new_audio_profile_or_runtime=False,
    old61_driving_tests_repeated=False,idle_listening_candidates_pending_no_duplicate_or_promotion=True,
    original_common_phase_qualification_remains_required=True,
    next='Use all actual failures and the new all48postfit band coverage before the next source model; inspect omitted upper-band structure rather than more low-optimizer sweeps. No arbitrary bass or source identity from local support.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation)
verify(root)
save(repo/'research/accel_candidate_prediction_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_candidate_prediction_v1','baselines/accel_candidate_prediction_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    'All48original F3 cubic/native/complete augmentation/masked prediction/adoption/graphs independently audited',
    'All failures/unknowns preserved;no sourceidentity/RPM/load/audio/runtime;612C-H67voices unchanged',
    'research/F3完整模型与预测V1.md | research/accel_candidate_prediction_v1_summary.json','baselines/accel_candidate_prediction_v1/validation.json'])
print(result)
