"""Freeze conditional idle amplitude source, all renders, controls and review."""
import argparse,subprocess,shutil
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/idle_conditioned_detail_v1'
root=a.workspace/'baselines/idle_conditioned_detail_v1';parent=a.workspace/'baselines/idle_microtexture_c_v1'
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
invariant=parent/'inputs';C=load(invariant/'C_files_sha256.json');voices=load(invariant/'voice_files_sha256.json')
assert len(C)==612 and len(voices)==67
for name,h in {**C,**voices}.items():assert sha(repo/name)==h,name
observed=load(evidence/'observe1/report.json');rendered=load(evidence/'trial1/report.json');audit=load(evidence/'audit1/report.json')
assert observed['result']=='conditional_amplitude_observed' and observed['candidate_gate'] and all(observed['supported_bands'])
assert rendered['result']=='conditioned_detail_candidates_pending_listening' and len(rendered['renders'])==9
assert audit['result']=='observation_parameters_and_all9_audio_verified' and len(audit['renders'])==9
assert sha(evidence/'trial1/report.json')==audit['input_report_sha256']
assert sha(evidence/'observe1/report.json')==audit['observation_sha256']==rendered['input_report_sha256']
assert rendered['zero_FLOAT_exact'] and audit['zero_FLOAT_exact'] and audit['maximum_FLOAT_error']<3e-8
assert sha(evidence/'observe1/model.json')==sha(evidence/'trial1/model.json')
review=load(evidence/'review1/report.json');assert review['common_gain']==1 and not review['listening_accepted']
for row in review['clips']:assert sha(evidence/'review1'/review['files'][row['key']])==row['sha256']
for row in review['inputs'].values():assert sha(row['path'])==row['sha256']
browser=load(evidence/'browser1/report.json');assert browser['result']=='pass' and browser['metadata_combinations']==25
plot=load(evidence/'plot1/report.json');assert plot['image_sha256']==sha(evidence/'plot1/conditional_idle.png')
shutil.copy2(evidence/'plot1/conditional_idle.png',repo/'research/idle_conditioned_detail_v1_diagnostics.png')
sources=set()
for folder,report in [('observe1',observed),('trial1',rendered)]:
    for name,h in report['sources'].items():
        assert sha(evidence/folder/'exact_sources'/name)==h and sha(repo/name)==h;sources.add(name)
sources.update(['tools/audit_idle_conditioned_detail_v1.py','tools/review_idle_conditioned_detail_v1.py',
    'tools/check_idle_conditioned_detail_v1.cjs','tools/plot_idle_conditioned_detail_v1.py','tools/package_idle_conditioned_detail_v1.py',
    'research/怠速主声线带动细节V1.md','research/idle_conditioned_detail_v1_diagnostics.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
frozen=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe'
inputs={'C_files_sha256.json':invariant/'C_files_sha256.json','voice_files_sha256.json':invariant/'voice_files_sha256.json',
    'F2_profile.json':frozen/'profile.json','F2_training.wav':frozen/'training.wav',
    'F2_check.wav':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
validation=dict(schema='vsl.idle-conditioned-detail-freeze/1',result='offline_amplitude_candidate_pending_listening',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    all4bands_positive_and_check_better_than_all3_phase_controls=True,
    check_MSE_improvement=observed['real']['check']['relative_mse_improvement'],
    all3seeds_and3amounts_retained=True,all9_independently_verified=True,zero_FLOAT_exact=True,
    maximum_FLOAT_error=audit['maximum_FLOAT_error'],C_H_unchanged=612,old_voices_unchanged=67,
    old61_driving_tests_repeated=False,same_recording_previously_inspected_check=True,
    engine_common_phase_qualification=False,physical_source_or_RPM_load_identified=False,
    original_shared_phase_gates_remain_required=True,room=False,recorded_timeline=False,PM_FM=False,
    runtime_changed=False,default_changed=False,timbre_accepted=False,
    browser_muted=True,browser_combinations=25,screenshots_and_plot_viewed=True,
    acceleration_amplitude_stage_remains_separate_unaudited=True,
    next='Hear candidate against prior fast50 for grain/sand/hum before optional generic C integration; do not infer full source recovery from small conditional MSE gains.')
result=freeze(root,repo,list(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_conditioned_detail_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_conditioned_detail_v1','baselines/idle_conditioned_detail_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'NativeF2 conditional bandPOWER;all3samePSD controls;all9audio independent reconstruction;25muted page combinations',
    'Small same-recording relation;NOT listening/enginephase/RPM/runtime acceptance;612C-H67voices unchanged',
    'research/怠速主声线带动细节V1.md | research/idle_conditioned_detail_v1_summary.json','baselines/idle_conditioned_detail_v1/validation.json'])
print(result)
