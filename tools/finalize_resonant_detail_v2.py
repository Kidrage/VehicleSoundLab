"""Bind feedback, protected-band renders and the parameter-only candidate."""
import argparse,csv,json,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False);root=a.workspace/'references/analysis/resonant_detail_v2'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
fit=read(root/'fit1/report.json');model=read(root/'fit1/detail_model.json')
render=read(root/'render1/report.json');review=read(root/'review1/report.json')
listening_path=repo/'research/resonant_detail_v2_listening.json';listening=read(listening_path)
assert listening['result']=='prior35_preferred_v2_not_adopted'
assert fit['result']=='fit_and_mask_controls_pass' and render['result']=='render_technical_pass'
assert review['result']=='review_technical_pass' and review['baseline_files_byte_exact']==25
for report in (fit,render):
    for name,digest in report['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in report['input_sha256'].items():assert sha(Path(name))==digest,name
assert sha(root/'fit1/detail_model.json')==fit['model_sha256']
assert sha(repo/'tools/review_resonant_detail_v2.py')==review['source_sha256']
assert sha(root/'review1/index.html')==review['page_sha256']
for row in review['clips']:assert sha(root/'review1'/row['file'])==row['sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
assert len(index)==478
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
assert sha(repo/'voices/resonant_detail_v1/detail.json')==model['inherited_filter_profile_sha256']
profile=dict(model)
profile['kernel_plan']={k:model['kernel_plan'][k] for k in ('sample_rate','cycle_frames','warmup_frames')}
profile['excitation']=dict(generator='xorshift64star/BoxMuller',
    band_seed_rule='seed XOR ((0x9E3779B97F4A7C15 * (band+1)) mod 2^64)',
    shared_between_observed_L_R=True)
profile['fitted_model_sha256']=fit['model_sha256']
voice=repo/'voices/resonant_detail_v2/detail.json';voice.parent.mkdir(parents=True,exist_ok=True)
voice.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
repeats={}
for i,name in enumerate(('1.2–1.9k','1.9–3k','3–6k','6–8k')):
    vals=[t['observation'][i]['repeat'][0]['maximum_repeat'] for t in render['trials']]
    repeats[name]=dict(original=render['original_observation'][i]['repeat'][0]['maximum_repeat'],
        prior35_first_seed=render['original35_observation'][i]['repeat'][0]['maximum_repeat'],
        protected_three_seed_range=[min(vals),max(vals)])
r=dict(schema='vsl.resonant-detail-summary/2',date='2026-11-12',result='offline_candidate_technical_pass_only',
    feedback_file='research/resonant_detail_v1_listening.json',
    prior35='retain_working_candidate_not_final_timbre_acceptance',prior70='rejected',
    candidate_listening=listening['result'],latest_feedback_file=listening_path.relative_to(repo).as_posix(),
    latest_feedback_sha256=sha(listening_path),moving_reference='hold_offline_v1_35_stop_moving_tuning',
    profile_file=voice.relative_to(repo).as_posix(),profile_sha256=sha(voice),
    harmonic_transition_hz=[3000,6000],maximum_harmonic_power_reduction=.35,
    harmonic_rows_below_3k_exact=True,active_detail_band_indices=[4,5,6,7],
    scalar_mask_error=fit['scalar_mask_error'],C_subtraction_error_FS=fit['C_subtraction_error_FS'],
    maximum_active_power_error_db=max(t['maximum_active_power_error_db'] for t in render['trials']),
    maximum_protected_change_db=max(t['maximum_protected_change_db'] for t in render['trials']),
    maximum_peak_FS_common_gain=max(t['peak_FS_after_common_gain'] for t in render['trials']),
    repeat_first_block_left=repeats,excitation_seeds=[t['seed'] for t in render['trials']],
    excitation_float_samples_exact_v1=all(t['excitation_float_samples_exact_v1'] for t in render['trials']),
    inherited_filters=True,independent_LF_preserved=True,new_room=False,C_H_unchanged=478,Ctests_not_repeated=47,
    no_native_default_driver_take_changes=True,manual_browser_interaction=False,
    review_URL=review['url'],review_clips=len(review['clips']),baseline_files_byte_exact=25,
    HTTP_FFmpeg_JS_pass=True,source_trajectory_stored=False,
    evidence_sha256={str(p.relative_to(root)).replace('\\','/'):sha(p) for p in
        (root/'fit1/report.json',root/'render1/report.json',root/'review1/report.json')},
    limits=['Human35 preference is conditional;70 is rejected despite similar band power',
        'One engineering taper, not a measured physical noise fraction or independent engine validation',
        'Same short normalized exterior context; no other state/RPM/engine acceptance',
        'Band energy and repeat measurements do not establish definition, naturalness or perceived brightness',
        'Protected harmonic rows are exact; detail bandpass skirts can change the total low-band signal',
        '3–6k repeat now exceeds the reference while6–8k remains overly periodic; no complete source match claimed'])
for path in (a.out/'report.json',repo/'research/resonant_detail_v2_summary.json'):
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps({k:r[k] for k in ('result','maximum_active_power_error_db','maximum_protected_change_db',
    'maximum_peak_FS_common_gain','review_URL')}))
