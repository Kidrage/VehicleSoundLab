"""Freeze the fixed D flame/audio observation and its non-promotion decision."""
import argparse,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/D_flame_audio_v1';root=a.workspace/'baselines/D_flame_audio_v1'
if a.verify:verify(root);print('D flame/audio archive verified');raise SystemExit
protected=a.workspace/'baselines/catalog_decel_v1';old=load(protected/'inputs/C_files_sha256.json');voices=load(protected/'inputs/voice_files_sha256.json')
assert len(old)==646 and len(voices)==74 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']:
    assert sha(repo/n)==sha(protected/'source'/n)
frames=load(e/'frames1/report.json');audio=load(e/'audio1/report.json');audit=load(e/'audit1/report.json');review=load(e/'review1/report.json')
assert len(frames['sources']['D']['frames'])==35 and audio['result']=='fixed_window_observed' and audit['result']=='passed'
assert audio['statistics']['candidate_count']==audio['statistics']['primary_candidate_count']==0 and audio['statistics']['maximum_two_band_excess_db']<6
assert review['result']=='four_original_clips_ready' and len(review['clips'])==4
assert load(e/'browser1/report.json')['result']==load(e/'browser2/report.json')['result']=='passed'
for n in ['desktop.png','mobile.png']:assert (e/'browser2'/n).is_file()
assert (e/'audio1/diagnostic.png').is_file()
for n,h in audio['source_files'].items():assert sha(repo/n)==h==sha(e/'audio1/exact_sources'/n)
assert sha(repo/'tools/inspect_idle_context_v1.py')==frames['source_sha256']==sha(e/'frames1/executed_inspect.py')
assert sha(repo/'tools/audit_D_flame_audio_v1.py')==sha(e/'audit1/executed_audit.py')
assert sha(repo/'tools/check_D_flame_audio_v1.cjs')==sha(e/'browser2/executed_check.cjs')
assert sha(e/'browser1/executed_check.cjs')!=sha(e/'browser2/executed_check.cjs')
sources=['tools/inspect_idle_context_v1.py','tools/drive_evidence_v1/sources.py','tools/observe_D_flame_audio_v1.py','tools/flame_audio_v1/measure.py',
 'tools/flame_audio_v1/review.html','tools/audit_D_flame_audio_v1.py','tools/review_D_flame_audio_v1.py','tools/check_D_flame_audio_v1.cjs',
 'tools/package_D_flame_audio_v1.py','tools/research_archive_v1.py','research/D_flame_audio_v1_plan.json','research/D_flame_audio_v1_frames.json',
 'research/D_flame_audio_v1_annotations.json','research/D台架火焰与爆音证据V1.md','references/segments_v1.json',
 'README.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md','research/怠速优化当前状态.md','research/E_decel_source_v1_listening.json']
validation=dict(result='fixed_D_flame_context_without_qualifying_acoustic_excess',git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
 protected_C_H=646,protected_voice_parameters=74,F2_exact=True,runtime_changed=False,new_event_timbre=False,
 new_trigger_mapping=False,new_source_PCM_loop=False,new_room=False,manual_hearing=False,source_seconds=[36,44],primary_seconds=[38,42],
 known_controls_before_source=audio['known_before_source'],original_PTS_frames=35,contact_sheets_viewed=5,observed_frames_step_seconds='0.233–0.234 (requested0.25 rounded to7 video frames)',
 numerical_candidate_count=0,maximum_two_band_excess_db=audio['statistics']['maximum_two_band_excess_db'],
 audit=audit,review_url=review['url'],raw_same_gain_clips=4,browser=load(e/'browser2/report.json'),
 analysis_and_browser_images_viewed=3,all_attempts_preserved=['frames1','audio1','audit1','review1','browser1','browser2'],
 numerical_failure_attempts=[],previous_CTests_not_repeated='No C/model/driver/UI/take change',
 decision='Keep fixed gates and mixed context; no independently qualified acoustic event, do not infer that no pop exists',
 scope='Training/reference observation, not RPM/fuel/load/AV/room/source separation or completed state timbre',
 idle_and_E_hearing_still_pending=True,full_goal='active',next='Inspect independent approved event/state material; no threshold/window rescue, default promotion or automatic higher-chaos work')
inputs={'C_files_sha256.json':protected/'inputs/C_files_sha256.json','voice_files_sha256.json':protected/'inputs/voice_files_sha256.json',
 'prior_system_manifest.json':protected/'manifest.json','data_AGENTS.md':a.workspace/'AGENTS.md','approval_manifest.json':a.workspace/'references/approval_manifest.json'}
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/D_flame_audio_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['D_flame_audio_v1','baselines/D_flame_audio_v1/manifest.json',result['file_count'],result['manifest_sha256'],
 '35PTSframes;8s native stereo;1597 direct FFT windows;4samegain clips;one-player clock/image checks',
 'No fixed-gate acoustic excess;flame is not pop/fuel/trigger proof;646C-H74voices exact;no hearing promotion',
 'research/D台架火焰与爆音证据V1.md | research/D_flame_audio_v1_summary.json','baselines/D_flame_audio_v1/validation.json'])
print(result)
