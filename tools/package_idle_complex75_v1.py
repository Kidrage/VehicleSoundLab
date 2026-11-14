"""Freeze the single native complex-envelope candidate, controls, failures and complete evidence."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_complex75_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_complex75_v1'
reports={name:load(evidence/name/'report.json') for name in ['fit1','render1','audit1','audit2','observe1','observation_audit1','assessment1','review1','browser1']}
assert reports['fit1']['result']=='source_native_complex75_fitted_pending_audit'
assert reports['render1']['result']=='finite_complex75_candidate_pending_audit'
assert reports['audit1']['result']=='failed' and 'all_fraction_covariance_cholesky' in reports['audit1']['error']
for name in ['audit2','observation_audit1','review1','browser1']:assert reports[name]['result']=='passed'
assert reports['observe1']['result']=='complete_actual_complex75_three_aperture_observation'
assert len(reports['observe1']['cases'])==288 and len(reports['observe1']['spectra'])==96
assert reports['observation_audit1']['window_QR']==33408 and reports['observation_audit1']['global_QR']==96
assert reports['assessment1']['audit_sha256']==sha(evidence/'observation_audit1/report.json')
assert reports['assessment1']['input_sha256']==reports['observation_audit1']['input_sha256']==sha(evidence/'observe1/report.json')
sources=set()
for folder in ['fit1','render1','observe1']:
    run=reports[folder]
    for path,digest in run['sources'].items():
        assert sha(repo/path)==digest==sha(evidence/folder/'exact_sources'/path);sources.add(path)
    for path,digest in run['inputs'].items():assert sha(path)==digest
for row in reports['render1']['renders']:
    assert sha(evidence/'render1'/row['driver_file'])==row['driver_sha256']
    for entry in row['files'].values():assert sha(evidence/'render1'/entry['file'])==entry['sha256']
for row in reports['observe1']['cases']+reports['observe1']['spectra']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,copy in [('tools/audit_idle_complex75_v1.py','audit2','executed_auditor.py'),
    ('tools/audit_idle_complex75_observation_v1.py','observation_audit1','executed_auditor.py'),
    ('tools/idle_short_budget_v1/independent.py','audit2','executed_independent.py'),
    ('tools/assess_idle_complex75_v1.py','assessment1','executed_assessment.py'),
    ('tools/review_idle_complex75_v1.py','review1','executed_review.py'),
    ('tools/idle_complex75_v1/review.html','review1','executed_template.html'),
    ('tools/check_idle_amplitude_v1.cjs','browser1','executed_check.cjs')]:
    assert sha(repo/path)==sha(evidence/folder/copy);sources.add(path)
assert reports['review1']['common_gain']==1. and len(reports['review1']['clips'])==reports['browser1']['metadata_combinations']==20
assert reports['review1']['audit_sha256']==sha(evidence/'audit2/report.json')
assert reports['review1']['observation_audit_sha256']==sha(evidence/'observation_audit1/report.json')
for row in reports['review1']['clips']:assert sha(evidence/'review1'/row['file'])==row['sha256']
fig=reports['assessment1']['figure'];assert sha(evidence/'assessment1'/fig['file'])==fig['sha256']
shutil.copy2(evidence/'assessment1'/fig['file'],repo/'research/idle_complex75_v1.png');sources.add('research/idle_complex75_v1.png')
shutil.copy2(evidence/'fit1/model.json',repo/'research/idle_complex75_v1_profile.json');sources.add('research/idle_complex75_v1_profile.json')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_idle_complex75_v1.py','research/怠速联合起伏V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in ['idle_short_budget_v1','idle_local_partition_v1','idle_phase_amplitude_v1','idle_phase_recipe_v1','idle_conditioned_detail_v1','fixed_source_profiles_v1']}
inputs.update(C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voices_path)
validation=dict(schema='vsl.idle-complex75-freeze/1',result='one_source_native_complex75_candidate_pending_hearing',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),human_priority='节奏太规整，像持续的合成器音符',
    TRAIN_only=True,CHECK_previously_seen=True,source_acoustic_phase_not_physical_separation=True,common_phase_estimator_not_newly_qualified=True,
    native_extraction_controls_before_fit=True,all480_joint_interpolation_covariances_checked=True,full_pre_history_fresh_gaussian_streams=True,
    theoretical_gain_power=1.,not_finite_take_or_RF_power_normalization=True,old75_AM_coupling_removed_in_both_new_branches=True,
    existing75detail_retained_not_physically_separated=True,source_PCM_or_coeff_timeline_looped=False,
    independent_native_all12_WAVs=True,maximum_WAV_error=reports['audit2']['errors']['all12_WAVs'],
    failed_independent_auditor_preserved='audit1 missing scipy lower=True in old Cholesky reconstruction; audit2 fixes verifier only, no production/data/gate changes',
    all3seeds24seconds=True,new_multibus_cases=288,reused_source_baseline_cases=168,window_QR=33408,global_QR=96,
    all51signed6x6_covariances_and96native_spectra_checked=True,phase_estimator_included=True,
    pooled=reports['assessment1']['pooled'],spectra=reports['assessment1']['spectra'],
    common_gain=1.,review_clips=20,review_url=reports['review1']['url'],browser_passed=True,figures_and_browser_screenshots_viewed=True,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,new_download=False,listening_accepted=False,
    next='Hear only this single new candidate against full frozen baseline and independent-old control; do not promote to C/default before evidence of benefit. Source3s acoustic-coordinate model remains provisional; retain original phase qualifications and full driving/multi-engine/stereo7.1.4 goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_complex75_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_complex75_v1','baselines/idle_complex75_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'nativejoint75;knownFM/AM;all12WAV;288cases33408QR96spectra;20browser',
    'onecandidateNOTaccepted;oldindependentcontrol;noC/default;619C-H67voices',
    'research/怠速联合起伏V1.md | research/idle_complex75_v1_summary.json','baselines/idle_complex75_v1/validation.json'])
print(result)
