"""Freeze the fixed B path failure, original playback and exact attempts."""
import argparse
from pathlib import Path
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--verify',action='store_true')
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
e=a.workspace/'references/analysis/B_shift_voice_v1'
root=a.workspace/'baselines/B_shift_voice_v1'
if a.verify:
    verify(root);print('B shift/local voice archive verified');raise SystemExit
protected=a.workspace/'baselines/catalog_decel_v1'
old=load(protected/'inputs/C_files_sha256.json')
voices=load(protected/'inputs/voice_files_sha256.json')
assert len(old)==646 and len(voices)==74 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource',
    'experiments/modal_texture_v1/F2_amplitude.mtexture',
    'experiments/spectral_texture_v1/F2_fine_static.sfir']
for name in f2:assert sha(repo/name)==sha(protected/'source'/name)
frames=load(e/'frames1/report.json')
fit=load(e/'fit1/report.json')
audit=load(e/'audit2/report.json')
review=load(e/'review1/report.json')
browser=load(e/'browser1/report.json')
assert len(frames['sources']['B']['frames'])==40
assert fit['result']=='fixed_centers_checked' and fit['accepted_count']==0 and fit['rejected_count']==2
assert fit['family']['status']=='no_connected_family' and not list(e.rglob('*.model'))
assert audit['result']=='passed' and audit['frames_checked']==1985 and audit['empty_reference_frames']==0
assert audit['reachability']['first_dead_seconds']==478.36
assert load(e/'audit1/report.json')['result']=='failed'
assert sha(e/'audit1/executed_audit.py')!=sha(e/'audit2/executed_audit.py')
assert review['result']=='three_original_clips_ready' and len(review['clips'])==3 and browser['result']=='passed'
assert review['failure_frontier']['minimum_required_octaves_per_second']>32
for n,h in fit['sources'].items():assert sha(repo/n)==h==sha(e/'fit1/exact_sources'/n)
for n,h in review['sources'].items():assert sha(repo/n)==h==sha(e/'review1/exact_sources'/n)
assert sha(repo/'tools/inspect_idle_context_v1.py')==frames['source_sha256']==sha(e/'frames1/executed_inspect.py')
assert sha(repo/'tools/audit_B_shift_voice_v1.py')==sha(e/'audit2/executed_audit.py')
assert sha(repo/'tools/check_B_shift_voice_v1.cjs')==sha(e/'browser1/executed_check.cjs')
for name in ('desktop.png','mobile.png'):assert (e/'browser1'/name).is_file()
sources=list(fit['sources'])+list(review['sources'])+[
    'tools/inspect_idle_context_v1.py','tools/audit_B_shift_voice_v1.py',
    'tools/check_B_shift_voice_v1.cjs','tools/package_B_shift_voice_v1.py',
    'research/B_shift_voice_v1_frames.json','research/B换挡局部声纹V1.md',
    'references/segments_v1.json','README.md','AGENTS.md',
    'handoff/研究续接.md','handoff/开发留痕.md','research/怠速优化当前状态.md',
    'research/E_decel_source_v1_listening.json']+f2
validation=dict(result='fixed_B_path_failed_without_local_voice_fit',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    protected_C_H=646,protected_voice_parameters=74,F2_exact=True,
    runtime_changed=False,new_DNA=False,new_C_render=False,new_trigger_mapping=False,
    new_source_PCM_loop=False,new_room=False,manual_hearing=False,
    source_seconds=[475,485],fixed_centers=[479,483],original_PTS_frames=40,contact_sheets_viewed=5,
    known_producer_controls_before_source=fit['known_apertures_before_source'],
    known_producer_family_before_source=fit['known_family_before_source'],
    audit=audit,failure_frontier=review['failure_frontier'],raw_same_gain_clips=3,
    browser=browser,analysis_and_browser_images_viewed=3,
    all_attempts_preserved=['frames1','fit1','audit1','audit2','review1','browser1'],
    interruption='audit1 exact floating equality across different summation implementations; retained, explicit scalar check in audit2',
    original_audio_gates_unchanged=True,previous_CTests_not_repeated='No C/model/driver/UI/take change',
    decision='Retain failure; neither fixed endpoint locally fitted. No anchor/window/ref/gate rescue',
    scope='One uninterrupted acoustic family unsupported; not proof of absent engine/local impossibility or physical RPM/load',
    idle_and_E_hearing_still_pending=True,full_goal='active',
    next='Independent supported state/audio work; no automatic failed-path rescue, idle migration, blind strengths or higher-chaos work',
    review_url=review['url'])
inputs={'C_files_sha256.json':protected/'inputs/C_files_sha256.json',
    'voice_files_sha256.json':protected/'inputs/voice_files_sha256.json',
    'prior_system_manifest.json':protected/'manifest.json',
    'data_AGENTS.md':a.workspace/'AGENTS.md',
    'approval_manifest.json':a.workspace/'references/approval_manifest.json'}
result=freeze(root,repo,sources,e,inputs,validation);verify(root)
save(repo/'research/B_shift_voice_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['B_shift_voice_v1','baselines/B_shift_voice_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '40PTSframes;1985direct FFT frames;observed peak reachability;3samegain originals;single-player source clock/offset pictures',
    'Original one-path gate fails478.360s;no local fit/model/C render;646C-H74voices F2 exact;idle/E hearing pending',
    'research/B换挡局部声纹V1.md | research/B_shift_voice_v1_summary.json','baselines/B_shift_voice_v1/validation.json'])
print(result)
