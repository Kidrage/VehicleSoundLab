"""Freeze phase-aware amplitude research and subsequent low-residual correction together."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_phase_amplitude_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_phase_amplitude_v1'
reports={name:load(evidence/name/'report.json') for name in ['observe1','observer_audit1','render1','render2','audit1',
         'review1','browser1','assessment1','diagnosis1','residual_render1','residual_audit1','residual_review1','residual_browser1','residual_assessment1']}
for name in ['observer_audit1','audit1','browser1','residual_audit1','residual_browser1']:assert reports[name]['result']=='passed'
assert reports['render1']['result']=='failed' and 'broadcast' in reports['render1']['error']
assert reports['observe1']['result']=='phase_aware_idle_amplitude_observed'
assert reports['render2']['result']=='finite_phase_aware_amplitude_audio_pending_audit'
assert reports['residual_render1']['result']=='finite_separated_low_residual_pending_audit'
assert len(reports['diagnosis1']['cases'])==24
sources=set()
for name in ['observe1','render2','residual_render1']:
    report=reports[name]
    for path,digest in report['inputs'].items():assert sha(path)==digest
    for path,digest in report['sources'].items():
        assert sha(repo/path)==digest==sha(evidence/name/'exact_sources'/path);sources.add(path)
# Preserve and verify failed executed bytes against their own manifest, not corrected source.
for path,digest in reports['render1']['sources'].items():assert sha(evidence/'render1/exact_sources'/path)==digest
for name in ['render2','residual_render1']:
    for row in reports[name]['renders']:
        for entry in row['files'].values():assert sha(evidence/name/entry['file'])==entry['sha256']
        if 'trace' in row:assert sha(evidence/name/row['trace'])==row['trace_sha256']
for review_name,browser_name,render_name in [('review1','browser1','render2'),('residual_review1','residual_browser1','residual_render1')]:
    review=reports[review_name];browser=reports[browser_name]
    assert len(review['clips'])==browser['metadata_combinations']==20 and review['common_gain']==1.
    assert review['input_report_sha256']==sha(evidence/render_name/'report.json')
    for clip in review['clips']:assert sha(evidence/review_name/review['files'][clip['key']])==clip['sha256']
executed=[('audit_idle_amplitude_observer_v1','observer_audit1','executed_auditor.py'),
          ('audit_idle_phase_amplitude_v1','audit1','executed_auditor.py'),
          ('review_idle_phase_amplitude_v1','review1','executed_review.py'),
          ('assess_idle_phase_amplitude_v1','assessment1','executed_assessment.py'),
          ('diagnose_idle_core_observer_v1','diagnosis1','executed_diagnostic.py'),
          ('audit_idle_separated_residual_v1','residual_audit1','executed_auditor.py'),
          ('review_idle_separated_residual_v1','residual_review1','executed_review.py'),
          ('assess_idle_separated_residual_v1','residual_assessment1','executed_assessment.py')]
for name,folder,copy in executed:
    path='tools/'+name+'.py';assert sha(repo/path)==sha(evidence/folder/copy);sources.add(path)
for folder,template in [('review1','review.html'),('residual_review1','residual_review.html')]:
    path='tools/idle_phase_amplitude_v1/'+template
    assert sha(repo/path)==sha(evidence/folder/'executed_template.html');sources.add(path)
for folder in ['browser1','residual_browser1']:
    assert sha(repo/'tools/check_idle_amplitude_v1.cjs')==sha(evidence/folder/'executed_check.cjs')
sources.add('tools/check_idle_amplitude_v1.cjs')
for folder,dest in [('assessment1','idle_phase_amplitude_v1.png'),('residual_assessment1','idle_separated_residual_v1.png')]:
    figure=reports[folder]['figure'];assert sha(evidence/folder/figure['file'])==figure['sha256']
    shutil.copy2(evidence/folder/figure['file'],repo/'research'/dest);sources.add('research/'+dest)
for folder,dest in [('render2','idle_phase_amplitude_v1_profile.json'),('residual_render1','idle_separated_residual_v1_profile.json')]:
    assert sha(evidence/folder/'model.json')==reports[folder]['model_sha256']
    shutil.copy2(evidence/folder/'model.json',repo/'research'/dest);sources.add('research/'+dest)
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voice_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voice_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
sources.update(['AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md','research/怠速主声线与残差V1.md','tools/package_idle_phase_amplitude_v1.py'])
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in
        ['idle_conditioned_detail_v1','fixed_source_profiles_v1','idle_phase_recipe_v1','idle_post_budget_v1','idle_local_shape_v1']}
inputs['old_voice_files_sha256.json']=voice_path
validation=dict(schema='vsl.idle-phase-amplitude-and-residual-freeze/1',result='source_based_idle_candidates_NOT_adopted',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observer_independent_QR_cases=13,observer_windows_each=116,source_train_only_fit=True,source_CHECK_already_inspected=True,
    source_main_log_std=reports['observe1']['observations'][0]['aware']['raw_log_std'],
    signed_amplitude_covariance_preserved_without_zero_clamp=True,
    first_render_failed_channel_index_preserved=True,finite_candidate_seeds=[149921,277139,381611],seconds_each=24,
    amplitude_candidate_maximum_wave_error_FS=max(v for row in reports['audit1']['renders'] for v in row['full_native_waveform_errors_FS'].values()),
    baseline_frozen_errors_FS=[row['zero_frozen_error_FS'] for row in reports['render2']['renders']],
    isolated_main_mix_diagnostic_cases=24,residual_source_projection_not_physical_separation=True,
    only_two_low_filter_shapes_recompiled=True,old_gains_and_innovations_preserved=True,
    residual_maximum_wave_error_FS=max(v for row in reports['residual_audit1']['renders'] for v in row['all_native_waveform_errors_FS'].values()),
    source_observer_results=reports['residual_assessment1']['generated_summary'],
    lower_112Hz_fluctuation_closer_187Hz_excess_and75Hz_deficit_remain=True,
    all619C_H_and67voices_exact=True,review_url=reports['residual_review1']['url'],
    separate_amplitude_url=reports['review1']['url'],each_review_clips=20,common_gain=1.,
    both_browsers_passed=True,figures_and_screenshots_viewed=True,runtime_changed=False,listening_accepted=False,
    accepted_moving_changed=False,original_phase_qualifications_and_full_goal_open=True,
    next='Listen to separated residual before C promotion; joint core AM/PM and residual power allocation, not arbitrary AM strength or notch sweep; retain all earlier pending reviews.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_phase_amplitude_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_phase_amplitude_v1','baselines/idle_phase_amplitude_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '13x116QR;3seedsxAM24s;projection+residual3x24s;2fullnativeaudits;2x20HTTPbrowser',
    '112Hzcloser;187excess75deficit;notphysicalAMPM;NOTadopted;619C-H67voicesexact',
    'research/怠速主声线与残差V1.md | research/idle_phase_amplitude_v1_summary.json','baselines/idle_phase_amplitude_v1/validation.json'])
print(result)
