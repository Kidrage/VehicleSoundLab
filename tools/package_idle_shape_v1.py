"""Freeze the weak but fully generated shape candidate without promoting it."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/idle_shape_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/idle_shape_v1'
trial=load(evidence/'trial1/report.json');audit=load(evidence/'audit1/report.json')
assessment=load(evidence/'assessment1/report.json');review=load(evidence/'review1/report.json');browser=load(evidence/'browser1/report.json')
assert trial['result']=='finite_phase_conditioned_shape_candidate_pending_audit_and_hearing'
assert audit['result']==browser['result']=='passed'
assert assessment['result']=='all72_shape_windows_observed_without_tuning' and len(assessment['observations'])==72
assert review['result']=='same_gain_single_player_shape_review' and len(review['clips'])==20 and review['common_gain']==1.
assert audit['input_report_sha256']==assessment['input_report_sha256']==review['input_report_sha256']==sha(evidence/'trial1/report.json')
assert assessment['audit_sha256']==review['audit_sha256']==sha(evidence/'audit1/report.json')
assert browser['metadata_combinations']==20 and browser['muted_playback']
sources=set(trial['sources'])
for name,digest in trial['sources'].items():assert sha(repo/name)==digest==sha(evidence/'trial1/exact_sources'/name)
assert sha(evidence/'trial1/model.json')==trial['model_sha256']
for row in trial['renders']:
    for entry in row['files'].values():assert sha(evidence/'trial1'/entry['file'])==entry['sha256']
    assert sha(evidence/'trial1'/row['trace_file'])==row['trace_sha256']
    x,rate=sf.read(evidence/'trial1'/row['files']['mix_0.0']['file'],always_2d=True)
    y,other=sf.read(row['old_frozen_mix_comparison']['reference'],frames=24*48000,always_2d=True)
    assert rate==other==48000 and np.array_equal(x,y)
for row in assessment['observations']:assert sha(evidence/'assessment1'/row['file'])==row['sha256']
for row in review['clips']:assert sha(evidence/'review1'/review['files'][row['key']])==row['sha256']
for name,directory,executed in [('tools/audit_idle_shape_v1.py','audit1','executed_auditor.py'),
    ('tools/assess_idle_shape_v1.py','assessment1','executed_assessment.py'),
    ('tools/review_idle_shape_v1.py','review1','executed_review.py'),
    ('tools/idle_shape_v1/review.html','review1','executed_template.html'),
    ('tools/check_idle_shape_v1.cjs','browser1','executed_check.cjs')]:
    assert sha(repo/name)==sha(evidence/directory/executed);sources.add(name)
sources.add('tools/idle_cyclic_detail_v1/observer.py')
prior=load(a.workspace/'baselines/idle_cyclic_detail_v1/evidence/observe1/report.json')
assert sha(repo/'tools/idle_cyclic_detail_v1/observer.py')==prior['sources']['tools/idle_cyclic_detail_v1/observer.py']
figure=assessment['figure'];assert sha(evidence/'assessment1'/figure['file'])==figure['sha256']
shutil.copy2(evidence/'assessment1'/figure['file'],repo/'research/idle_shape_v1_cyclic_gap.png')
shutil.copy2(evidence/'trial1/model.json',repo/'research/idle_shape_v1_profile.json')
sources.update(['research/idle_shape_v1_cyclic_gap.png','research/idle_shape_v1_profile.json','research/怠速共振形状试听V1.md',
    'tools/package_idle_shape_v1.py','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
rows=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(rows)==620 and all(sha(repo/row[0])==row[4] for row in rows[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/k)==v for k,v in voices.items())
parents=['idle_conditioned_detail_v1','fixed_source_profiles_v1','idle_phase_recipe_v1','idle_positive_power_v1','idle_post_budget_v1','idle_cyclic_detail_v1']
inputs={name+'_manifest.json':a.workspace/'baselines'/name/'manifest.json' for name in parents}
tables={name:{v['path']:v['sha256'] for v in load(a.workspace/'baselines'/name/'manifest.json')['files']} for name in parents}
for name,digest in trial['inputs'].items():
    path=Path(name);assert sha(path)==digest
    rel=path.relative_to(a.workspace/'baselines');assert tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]==digest
inputs['old_voice_files_sha256.json']=voices_path;inputs['data_workspace_AGENTS']=a.workspace/'AGENTS.md'
validation=dict(schema='vsl.idle-shape-freeze/1',result='small_source_shape_candidate_weak_gain_NOT_adopted',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    seeds=[149921,277139,381611],amounts=[0.,.5,1.],seconds_each=24,all3frozen_zero_samples_exact=True,
    all72windows_observed=True,all12old_cyclic_curves_exact=True,
    all3seeds_allamounts_native_independent_audit=True,source_and_control_branch_fits=4,
    shape_bounds=load(evidence/'trial1/model.json')['delta_bounds'],
    source_branch_comparison=assessment['source_branch_assessment'],
    cyclic_medians={k:v['median_train_check'] for k,v in assessment['summaries'].items()},
    maximum_peak_FS=max(item['peak'] for row in trial['renders'] for item in row['files'].values()),
    gain_is_small=True,perceptual_improvement_unproven=True,
    review_url=review['url'],review_clips=20,common_gain=1.,browser=browser,
    statistical_plot_and_desktop_mobile_viewed=True,existing619C_H_and67voices_exact=True,
    runtime_changed=False,accepted_moving35_changed=False,recorded_PCM_timeline_replayed=False,
    listening_accepted=False,
    next='Do not promote or amplify this weak broad-two-branch AM hypothesis. Old common q already explains most observed branch benefit; separate branch CHECK changes are mixed. New finite page available without duplicate listening question. If continuing waveform-shape study, fit source complex covariance using a positive conditional resonant-kernel factor; no independent HF cloud or endless scalar gain/window sweeps. Preserve pending auditions, original phase qualifications and full goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/idle_shape_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_shape_v1','baselines/idle_shape_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '4source/controlfits;3seedsx3amountsx24s;independentallnative/Gram;72windows;20HTTPbrowser',
    'Weak0.12/0.15percentmetricgain;oldqexplainsmost;noCpromotion;619C-H67voicesexact',
    'research/怠速共振形状试听V1.md | research/idle_shape_v1_summary.json','baselines/idle_shape_v1/validation.json'])
print(result)
