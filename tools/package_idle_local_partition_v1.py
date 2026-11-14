"""Freeze source allocation, one failed known control, joint compiler and finite audio."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/idle_local_partition_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_local_partition_v1'
reports={name:load(evidence/name/'report.json') for name in ['observe1','audit1','assessment1','compile1','compile2','render1',
          'audio_audit1','profile_binding1','audio_assessment1','review1','browser1']}
assert reports['observe1']['result']=='local_selected_core_partition_observed' and len(reports['observe1']['cases'])==80
assert reports['compile1']['result']=='failed' and reports['compile1']['error']=='AssertionError()'
assert reports['compile2']['result']=='joint_coherent_and_low_residual_budget_compiled'
assert reports['render1']['result']=='finite_idle_joint_budget_pending_audit'
for name in ['audit1','audio_audit1','profile_binding1','browser1']:assert reports[name]['result']=='passed'
assert reports['audit1']['local_QR_windows']==1840
assert reports['profile_binding1']['model_sha256']==reports['compile2']['model_sha256']
assert reports['profile_binding1']['audio_audit_sha256']==sha(evidence/'audio_audit1/report.json')
sources=set()
for folder in ['observe1','compile2','render1']:
    report=reports[folder]
    for path,digest in report['inputs'].items():assert sha(path)==digest
    for path,digest in report['sources'].items():
        assert sha(repo/path)==digest==sha(evidence/folder/'exact_sources'/path);sources.add(path)
for path,digest in reports['compile1']['sources'].items():assert sha(evidence/'compile1/exact_sources'/path)==digest
for case in reports['observe1']['cases']:assert sha(evidence/'observe1'/case['file'])==case['sha256']
for row in reports['render1']['renders']:
    assert sha(evidence/'render1'/row['nodes_file'])==row['nodes_sha256']
    for item in row['files'].values():assert sha(evidence/'render1'/item['file'])==item['sha256']
assert sha(evidence/'compile2/model.json')==reports['compile2']['model_sha256']
assert sha(evidence/'compile2/spectra.npz')==reports['compile2']['spectra_sha256']
assert len(reports['review1']['clips'])==reports['browser1']['metadata_combinations']==20
assert reports['review1']['common_gain']==1. and reports['browser1']['defaults_stopped']
assert reports['review1']['input_report_sha256']==sha(evidence/'render1/report.json')
assert reports['review1']['audit_sha256']==sha(evidence/'audio_audit1/report.json')
for row in reports['review1']['clips']:assert sha(evidence/'review1'/row['file'])==row['sha256']
executed=[('tools/audit_idle_local_partition_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_idle_local_partition_v1.py','assessment1','executed_assessment.py'),
    ('tools/audit_idle_local_partition_audio_v1.py','audio_audit1','executed_auditor.py'),
    ('tools/verify_idle_joint_budget_profile_v1.py','profile_binding1','executed_verifier.py'),
    ('tools/assess_idle_joint_budget_v1.py','audio_assessment1','executed_assessment.py'),
    ('tools/review_idle_joint_budget_v1.py','review1','executed_review.py'),
    ('tools/research_audio_review_v1.py','review1','executed_exporter.py'),
    ('tools/idle_local_partition_v1/review.html','review1','executed_template.html'),
    ('tools/check_idle_amplitude_v1.cjs','browser1','executed_check.cjs')]
for path,folder,copy in executed:
    assert sha(repo/path)==sha(evidence/folder/copy);sources.add(path)
for folder,dest in [('assessment1','idle_local_partition_v1.png'),('audio_assessment1','idle_local_partition_audio_v1.png')]:
    figure=reports[folder]['figure'];assert sha(evidence/folder/figure['file'])==figure['sha256']
    shutil.copy2(evidence/folder/figure['file'],repo/'research'/dest);sources.add('research/'+dest)
shutil.copy2(evidence/'compile2/model.json',repo/'research/idle_local_partition_audio_v1_profile.json');sources.add('research/idle_local_partition_audio_v1_profile.json')
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
old_auditor=a.workspace/'baselines/idle_joint_budget_v1/source/tools/audit_idle_joint_budget_v1.py'
assert sha(repo/'tools/audit_idle_joint_budget_v1.py')==sha(old_auditor)
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
sources.update(['AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md','research/怠速主声线功率分配V1.md',
               'tools/package_idle_local_partition_v1.py'])
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in
        ['idle_phase_amplitude_v1','idle_conditioned_detail_v1','fixed_source_profiles_v1','idle_phase_recipe_v1','idle_local_shape_v1']}
inputs['old_voice_files_sha256.json']=voices_path;inputs['C_H_index.csv']=repo/'handoff/C文件索引.csv'
inputs['preserved_historical_auditor.py']=old_auditor
source=reports['assessment1']['sources'];source=[v for v in source if v['metadata']['kind']=='source']
validation=dict(schema='vsl.idle-local-partition-and-joint-budget-freeze/1',result='source_allocation_and_finite_audio_NOT_adopted',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    all80partitions_independently_checked=True,local_QR_windows=1840,known_AM_FM_and_fast_neighbor_controls_preserved=True,
    source_187_near_line_dynamic_static_residual_ratio=[v['near_line_dynamic_static_residual_ratio'][2] for v in source],
    source_maximum_cross_fraction_original7bands=[v['maximum_absolute_cross_fraction_original7bands'] for v in source],
    source_CHECK_previously_inspected=True,TRAIN_only_fit=True,failed_odd81_known_compile_preserved=True,
    source_3main_RMS_LR=reports['compile2']['main_amplitude_LR'],
    old_low_gains=reports['compile2']['old_low_gains'],new_low_gains=reports['compile2']['new_low_gains'],
    all9band_expected_predictions=reports['compile2']['assessment'],source_cross_and_AM_PM_limits_remain=True,
    both_actual_LR_gains_bound=True,gain_binding_error=reports['profile_binding1']['actual_rendered_gain_squared_binding_error'],
    three_fixed_seeds=[149921,277139,381611],seconds_each=24,conditions=reports['audio_assessment1']['conditions'],
    all_native_audio_checked=True,maximum_native_audio_error_FS=max(v for row in reports['audio_audit1']['renders'] for v in row['all_native_waveform_error_FS'].values()),
    source_PCM_or_coefficient_trajectory_looped=False,prior_baseline_samples_exact=True,
    old619C_H_and67voices_exact=True,historical_auditor_restored_byte_exact=True,
    new_audio_auditor_renamed_without_changing_executed_bytes=True,
    accepted_moving_changed=False,runtime_changed=False,listening_accepted=False,
    review_url=reports['review1']['url'],review_clips=20,common_gain=1.,browser_passed=True,figures_and_screenshots_viewed=True,
    next='Hear joint allocation before C promotion. Keep75Hz residual/AM and AM-PM coupling limits explicit; do not arbitrary boostAM/notch187 or infer physical sources from local-fit reduction. Preserve original phase qualifications, pending auditions and full driving/multi-engine/7.1.4 goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_local_partition_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_local_partition_v1','baselines/idle_local_partition_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '80partitions1840QR;sourceexactPSD/2x2LR;3x3x24sallnative;72blocks;20HTTPbrowser',
    '187fluctcloser;75AMgap;sourcecrossnotphysical;NOTadopted;619C-H67voicesexact',
    'research/怠速主声线功率分配V1.md | research/idle_local_partition_v1_summary.json','baselines/idle_local_partition_v1/validation.json'])
print(result)
