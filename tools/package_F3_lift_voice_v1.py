"""Freeze the fixed F3 observations, corrected seed host and all failed attempts."""
import argparse
import csv
import io
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--verify',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];e=a.workspace/'references/analysis/F3_lift_voice_v1';root=a.workspace/'baselines/F3_lift_voice_v1'
if a.verify:verify(root);print('F3 local voice archive verified');raise SystemExit
protected=a.workspace/'baselines/bench_load_ui_v1/inputs'
old=load(protected/'C_files_sha256.json');voices=load(protected/'voice_files_sha256.json')
assert len(old)==646 and len(voices)==74 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
fit=load(e/'fit2/report.json');audit=load(e/'audit3/report.json');build=load(e/'build1/report.json')
review=load(e/'review1/report.json');browser=load(e/'browser1/report.json')
assert fit['qualified']==1 and fit['excluded']==2 and audit['result']==build['result']==browser['result']=='passed'
assert audit['frames_checked']==535 and build['correction']['old_seed_labels_invalid']
assert sha(e/'fit1/report.json')==build['correction']['original_report_sha256']
assert load(e/'audit1/report.json')['result']==load(e/'audit2/report.json')['result']=='failed'
assert len(review['clips'])==7 and all(sha(e/'review1'/v['file'])==v['sha256'] for v in review['clips'])
for attempt in ('build1','fit2','audit3','review1'):
    for n,h in load(e/attempt/'report.json')['sources'].items():assert sha(repo/n)==h==sha(e/attempt/'exact_sources'/n)
assert sha(repo/'tools/check_F3_lift_voice_v1.cjs')==sha(e/'browser1/executed_check.cjs')
frames=a.workspace/'references/analysis/F3_lift_context_v1/inspect1'
assert len(load(frames/'report.json')['sources']['F3']['frames'])==25
if not (e/'context_inspect1').exists():shutil.copytree(frames,e/'context_inspect1')
assert sha(e/'context_inspect1/report.json')==sha(frames/'report.json')
f2=['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']
for n in f2:assert sha(repo/n)==sha(a.workspace/'baselines/catalog_decel_v1/source'/n)
index=repo/'handoff/C文件索引.csv';rows=list(csv.reader(index.open(encoding='utf-8-sig')))
assert len(rows)==648 and all(sha(repo/v[0])==v[4] for v in rows[1:])
assert len(set(v[0] for v in rows[1:]))==647
names=subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=repo).decode('utf-8').split('\0')
actual={n for n in names if Path(n).suffix.lower() in ('.c','.h')}
assert actual=={v[0] for v in rows[1:]}
source_names=set(f2)|set(fit['sources'])|set(build['sources'])|set(audit['sources'])|set(review['sources'])
source_names.update(['tools/package_F3_lift_voice_v1.py','tools/check_F3_lift_voice_v1.cjs',
    'experiments/sound_dna_export_v1/README.md','research/F3_lift_context_v1_plan.json',
    'research/F3_lift_context_v1_inspection_plan.json','research/F3_lift_context_v1_annotations.json',
    'research/F3后加速局部声线V1.md','references/segments_v1.json','README.md','AGENTS.md',
    'handoff/C文件索引.csv','handoff/C模块与接口.md','handoff/研究续接.md','handoff/开发留痕.md',
    'research/E_decel_source_v1_listening.json'])
validation=dict(result='one_fixed_local_F3_mainline_two_excluded',
    git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    original_C_H_exact=646,new_offline_C_H=1,current_index_C_H=647,voice_parameters_exact=74,F2_exact=True,
    runtime_changed=False,default_changed=False,new_event_or_state_mapping=False,new_room=False,
    source_seconds=[199.5,205.5],original_PTS_frames=25,contact_sheets_previously_viewed=4,
    qualified=1,excluded=2,root_hz=fit['cases'][0]['extraction']['root_hz'],
    acoustic_gates_unchanged=True,physical_RPM_or_load=False,new_seed_protocol='vsl.sound-dna-raw-export/1',
    corrected_render_interface=build['correction'],build_checks=build,audit=audit,browser=browser,
    source_review_url=review['url'],audition_clips=7,source_and_browser_images_viewed=3,
    all_attempts_preserved=['context_inspect1','inputs','fit1','build1','fit2','audit1','audit2','audit3','review1','browser1'],
    failed_attempt_reasons=['fit1 mislabeled legacy output-selector as seed; extraction unaffected',
        'audit1 finite real-tone opposite-frequency leakage invalidated exact analytic cross reference before source read',
        'audit2 fixed3e-8FS tolerance failed FLOAT rounding above1FS; audit3 uses exact FLOAT sample equality'],
    spectral_diagnostics=load(e/'review1/band_metrics.json'),new_listening_acceptance=False,
    old_CTests_not_repeated='Original runtime/646C-H unchanged; isolated new offline host built and checked',
    idle_complex75_hearing='independently pending, no migration or blind strengths',
    E_stereo_feedback='左右关系有改善，音色仍明显电子',full_goal='active',
    next='Analyze F3 local residual and joint stereo detail from this fixed source; no physical state mapping or moving35 transfer without evidence')
inputs={'C_files_sha256.json':protected/'C_files_sha256.json','voice_files_sha256.json':protected/'voice_files_sha256.json',
    'prior_system_manifest.json':a.workspace/'baselines/bench_load_ui_v1/manifest.json',
    'approval_manifest.json':a.workspace/'references/approval_manifest.json','data_AGENTS.md':a.workspace/'AGENTS.md'}
result=freeze(root,repo,source_names,e,inputs,validation);verify(root)
save(repo/'research/F3_lift_voice_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_lift_voice_v1','baselines/F3_lift_voice_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '25PTSframes;535direct FFT frames;exact native/normalized samples;carrier/parameters/seeded C checks;7single-player clips',
    '1local DNA2excluded;fixed seed CLI corrected;646oldC-H74voices/F2 exact;1offline C added;no state/default promotion',
    'research/F3后加速局部声线V1.md | research/F3_lift_voice_v1_summary.json','baselines/F3_lift_voice_v1/validation.json'])
print(result)
