"""Freeze native idle concentration and every fast-detail audio candidate."""
import argparse,subprocess
from pathlib import Path
from research_archive_v1 import sha,load,save,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];evidence=a.workspace/'references/analysis/idle_microtexture_v1'
root=a.workspace/'baselines/idle_microtexture_v1';parent=a.workspace/'baselines/fine_idle_drive_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
assert len(old)==600 and len(voices)==67 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
if a.stage=='verify':verify(root);print('freeze verified');raise SystemExit
observed=load(evidence/'observe1/report.json');rendered=load(evidence/'trial1/report.json');audit=load(evidence/'audit1/report.json')
assert observed['result']=='fixed_idle_short_time_concentration_observed' and len(observed['observations'])==17
assert rendered['result']=='fast_detail_candidates_pending_listening' and len(rendered['renders'])==9
assert audit['result']=='train_only_statistics_and_all9_fast_detail_renders_verified'
assert audit['input_report_sha256']==sha(evidence/'trial1/report.json')
assert audit['zero_FLOAT_exact'] and rendered['zero_FLOAT_exact'] and audit['maximum_FLOAT_error']<3e-8
sources=set()
for folder,report in [('observe1',observed),('trial1',rendered)]:
    for name,h in report['sources'].items():
        assert sha(evidence/folder/'exact_sources'/name)==h and sha(repo/name)==h;sources.add(name)
for name in ['review1','review2']:
    review=load(evidence/name/'report.json');assert review['common_gain']==1 and not review['listening_accepted']
    for clip in review['clips']:assert sha(evidence/name/review['files'][clip['key']])==clip['sha256']
    assert load(evidence/name.replace('review','browser')/'report.json')['result']=='pass'
assert load(evidence/'plot1/report.json')['image_sha256']==sha(repo/'research/idle_microtexture_v1_diagnostics.png')
frozen=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe'
for row in observed['observations']:
    if row['name']=='F2_train':assert row['input_sha256']==sha(frozen/'training.wav')
    if row['name']=='F2_check':assert row['input_sha256']==sha(a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav')
sources.update(['tools/audit_idle_microtexture_v1.py','tools/review_idle_microtexture_v1.py','tools/check_idle_microtexture_v1.cjs',
    'tools/plot_idle_microtexture_v1.py','tools/package_idle_microtexture_v1.py','research/怠速快速颗粒V1.md',
    'research/idle_microtexture_v1_diagnostics.png','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
validation=dict(schema='vsl.idle-microtexture-freeze/1',result='audible_fast_detail_candidates_pending_listening',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observations=17,renders=9,all_seeds_retained=True,independent_FLOAT_error=audit['maximum_FLOAT_error'],
    independent_state_error=audit['maximum_state_error'],zero_FLOAT_exact=True,training_only=True,
    data_covariance_positive_without_projection=True,evidence=rendered['evidence'],
    source_modulation_is_proxy=True,profile_has_no_source_trajectory=True,room=False,
    short_time_concentration_partly_recovered_not_matched=True,timbre_acceptance=False,runtime_changed=False,
    C_H_unchanged=600,voices_unchanged=67,old61CTest_repeated=False,
    both_browser_attempts_preserved=True,browser_muted=True,screenshots_and_plot_viewed=True,
    original_idle_question_repeated=False,
    next='Listen to existing baseline/50/100 contrast for grain versus sand/tremor before C adoption; finite10ms proxy does not establish physical combustion or RPM.')
inputs={'C_files_sha256.json':parent/'inputs/C_files_sha256.json','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'F2_parent_profile.json':frozen/'profile.json','F2_training.wav':frozen/'training.wav',
    'F2_check.wav':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav','data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,list(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_microtexture_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_microtexture_v1','baselines/idle_microtexture_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'NativeF2 fast concentration/samePSD controls;train-only positive excess covariance;all9audio independent replay;19muted page combinations',
    'Improves finite concentration partly;NOT listening/physicalAM/commonphase/RPM/runtime acceptance;600C-H67voices unchanged',
    'research/怠速快速颗粒V1.md | research/idle_microtexture_v1_summary.json','baselines/idle_microtexture_v1/validation.json'])
print(result)
