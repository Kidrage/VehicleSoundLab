"""Freeze source-specific additive detail, tests and its unaccepted listening boundary."""
import argparse
import csv
from pathlib import Path
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/F3_detail_v1';root=a.workspace/'baselines/F3_detail_v1'
if a.verify:verify(root);print('F3 additive detail archive verified');raise SystemExit
parent=a.workspace/'baselines/F3_lift_voice_v1';verify(parent)
old=list(csv.DictReader((parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(old)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in old)
voices=load(parent/'inputs/voice_files_sha256.json');assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
index=list(csv.DictReader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert index==old
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
for n in f2:assert sha(repo/n)==sha(parent/'source'/n)
observation=load(e/'observe1/report.json');fit=load(e/'fit1/report.json');audit=load(e/'audit1/report.json')
review=load(e/'review1/report.json');browser=load(e/'browser1/report.json')
assert observation['result']=='fixed_residual_observed' and observation['positive_debt_bands']==10
assert fit['result']=='fixed_additive_residual_candidate_rendered' and len(fit['models'])==10 and not fit['skipped']
assert audit['result']==browser['result']=='passed' and audit['C_actual_profile_zero_warmup_oracle_error_FS']<2e-11
assert review['result']=='seven_additive_detail_clips_ready' and len(review['clips'])==7
sources=set(f2)
for attempt in ('observe1','fit1','audit1','review1'):
    report=load(e/attempt/'report.json')
    for n,h in report['sources'].items():assert sha(repo/n)==h==sha(e/attempt/'exact_sources'/n);sources.add(n)
for row in review['clips']:assert sha(e/'review1'/row['file'])==row['sha256']
assert sha(repo/'tools/check_F3_lift_voice_v1.cjs')==sha(e/'browser1/executed_check.cjs')
sources.update(['tools/package_F3_detail_v1.py','tools/check_F3_lift_voice_v1.cjs','research/F3双声道残差细节V1.md',
    'README.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md','handoff/C模块与接口.md',
    'research/E_decel_source_v1_listening.json'])
validation=dict(result='fixed_F3_additive_stereo_residual_candidate_unaccepted',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    C_H_exact=647,voice_parameters_exact=74,F2_exact=True,runtime_changed=False,
    new_C=False,new_default=False,new_driver_or_state_mapping=False,new_room=False,
    complete_cycles=14,periodic_residual_power_support_bands=[v['band_hz'] for v in observation['source_dependence']['bands'] if v['periodic_residual_power_supported']],
    periodic_residual_modulation_qualified=False,physical_source_separation=False,
    source_controls=observation['known_before_source'],predictor_controls=fit['known_before_source'],
    positive_debt_bands=10,models=10,pole_radii=[v['pole_radius'] for v in fit['models']],
    profile_sha256=fit['profile_sha256'],same_DNA=True,withdrawal=0,
    trials=fit['trials'],audit=audit,browser=browser,review_url=review['url'],
    listening_question='request_user_input_async: main versus additive detail and detail solo; pending',
    hearing_accepted=False,analysis_and_UI_images_viewed=3,
    all_attempts_preserved=['observe1','fit1','audit1','review1','browser1'],no_failed_refit_or_seed_selection=True,
    previous66CTest_not_repeated='No C/driver/UI/default/take modification; existing C kernels checked on actual new parameters',
    idle_complex75_hearing='still independently pending; no blind strengths or migration',
    E_stereo_feedback='左右关系有改善，音色仍明显电子',full_goal='active',
    next='Known stationary noise through identical phase extraction/warp to distinguish highband processing imprint from source dependence; await this independent detail hearing before any timbre promotion')
inputs={'C_index_before.csv':parent/'source/handoff/C文件索引.csv','voice_files_sha256.json':parent/'inputs/voice_files_sha256.json',
    'prior_manifest.json':parent/'manifest.json','approval_manifest.json':a.workspace/'references/approval_manifest.json','data_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/F3_detail_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_detail_v1','baselines/F3_detail_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '14cycle residual;heldout phase-power/null;10VAR24profiles;3x32sC;direct spectra/profile oracle;7clip browser',
    '647C-H74voices/F2 exact;unchanged DNA+additive detail;no room/state/default/physical-source promotion;hearing pending',
    'research/F3双声道残差细节V1.md | research/F3_detail_v1_summary.json','baselines/F3_detail_v1/validation.json'])
print(result)
