"""Freeze both native low-fit attempts, including the original unit failure."""
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
ids=['accel_low_fit_v1','accel_low_profiled_v1']
if a.stage=='verify':
    for key in ids:
        verify(a.workspace/'baselines'/key)
    print('Both low joint-fit freezes verified.')
    raise SystemExit
roots=[a.workspace/'references/analysis'/key for key in ids]
observations=[roots[0]/'observe2',roots[1]/'observe1']
reports=[load(path/'report.json') for path in observations]
audits=[load(root/'audit1/report.json') for root in roots]
plot=load(roots[1]/'plot1/report.json')
assert reports[0]['result']=='all48_native_low_upper_joint_fits_and_temporal_checks_complete'
assert reports[1]['result']=='all48_exact_profiled_native_fits_and_temporal_checks_complete'
assert audits[0]['result']=='all_known_and48_native_waves_initials_tracks_phase_reports_predictions_verified'
assert audits[1]['result']=='all_profiled_controls_left_LS_reduced_gradient_64native_waves_tracks_predictions_verified'
for i in range(2):
    assert sha(observations[i]/'report.json')==audits[i]['input_report_sha256']==plot['input_report_sha256'][i]
    assert sha(roots[i]/'audit1/report.json')==plot['audit_report_sha256'][i]
    assert audits[i]['waveforms']==64 and audits[i]['lines']==2073
    assert sum(v['compared_low_tracks'] for v in reports[i]['observations'])==0
assert sum(v['successful'] for v in reports[0]['observations'])==21
assert sum(v['successful'] for v in reports[1]['observations'])==26
failed=load(roots[0]/'observe1/report.json')
assert failed['result']=='failed' and failed['observations']==[]
assert (roots[0]/'observe1/known_progress').is_dir()
for filename,target in [('fit_status.png','status'),('low_tracks.png','tracks')]:
    path=roots[1]/'plot1'/filename
    assert sha(path)==plot['images'][filename]
    shutil.copy2(path,repo/f'research/accel_low_joint_v1_{target}.png')
sources=set()
for root in roots:
    for child in root.iterdir():
        if (child/'report.json').is_file():
            r=load(child/'report.json')
            for name,h in r.get('sources',{}).items():
                assert sha(child/'exact_sources'/name)==h
for report in reports:
    for name,h in report['sources'].items():
        assert sha(repo/name)==h
        sources.add(name)
sources.update(['tools/audit_accel_low_fit_v1.py','tools/audit_accel_low_profiled_v1.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py',
    'tools/plot_accel_low_joint_v1.py','tools/package_accel_low_joint_v1.py',
    'research/加速低频联合拟合V1.md','research/accel_low_joint_v1_status.png','research/accel_low_joint_v1_tracks.png',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
invariants=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
inputs={'data_workspace_AGENTS.md':a.workspace/'AGENTS.md',
    'low_inventory_manifest.json':a.workspace/'baselines/accel_low_inventory_v1/manifest.json',
    'ridges_manifest.json':a.workspace/'baselines/accel_ridges_v1/manifest.json'}
for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    table=load(invariants/filename)
    assert len(table)==count
    for name,h in table.items():
        assert sha(repo/name)==h
    inputs[filename]=invariants/filename
parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
for i,key in enumerate(ids):
    local_inputs=dict(inputs)
    if i:
        local_inputs['joint_fit_manifest.json']=a.workspace/'baselines'/ids[0]/'manifest.json'
    validation=dict(schema='vsl.native-low-joint-freeze/1',result='all48_fits_audited_NO_qualified_low_track_or_new_sound',
        parent_commit=parent_commit,method=key,observations=reports[i]['observations'],
        native_source_lines=1942,known_and_actual_waveforms=64,including_known_fitted_lines=2073,
        audit=audits[i],original_unit_failure_retained=True,all_failed_windows_retained=True,
        original_model_bounds_budget_and_gates_unchanged=True,low_tracks_atleast5=0,
        both_plots_viewed=True,no_gap_bridging=True,common_phase_RPM_load_or_source_identity=False,
        original_common_phase_qualification_remains_required=True,new_audio_or_runtime_profile=False,
        C_H_unchanged=612,old_voices_unchanged=67,old61_tests_repeated=False,
        idle_candidate_pending_no_duplicate_question_or_blind_tune=True,
        next='Prioritize pending idle sound judgement. Diagnose known AM/nonlinearFM and mono-noise local model/continuity before further low source design; no budget/range/threshold sweeps.')
    result=freeze(a.workspace/'baselines'/key,repo,sorted(sources),roots[i],local_inputs,validation)
    verify(a.workspace/'baselines'/key)
    save(repo/'research'/(key+'_summary.json'),dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[key,'baselines/'+key+'/manifest.json',result['file_count'],result['manifest_sha256'],
        'All48native fits;64known/actual cases independently audited;original failure retained;'+str(sum(v['successful'] for v in reports[i]['observations']))+' successful windows',
        'No continuous low track/profile/audio;612C-H67voices unchanged;idle listening pending',
        'research/加速低频联合拟合V1.md | research/'+key+'_summary.json','baselines/'+key+'/validation.json'])
    print(dict(study=key,**result))
