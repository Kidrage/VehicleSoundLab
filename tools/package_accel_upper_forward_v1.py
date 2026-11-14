"""Freeze native shared-iid forward evidence without creating or promoting a voice."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index
root=a.workspace/'baselines/accel_upper_forward_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_forward_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json')
first=load(evidence/'assessment1/report.json');assessment=load(evidence/'assessment2/report.json')
assert run['result']=='all12_shared_iid_forward_probes_complete' and len(run['observations'])==12
assert audit['result']=='passed' and audit['observations']==12 and audit['pairs']==192
assert assessment['result']==first['result']=='all12_forward_probes_assessed_not_a_voice'
assert audit['input_sha256']==assessment['input_sha256']==first['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['audit_sha256']==first['audit_sha256']==sha(evidence/'audit1/report.json')
assert assessment['segments']==first['segments'] and assessment['unavailable_pairs']==first['unavailable_pairs']==90
sources=set(run['sources'])
for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path)
parent=a.workspace/'baselines/accel_upper_joint_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
for path,digest in run['parent_files'].items():assert sha(parent/path)==digest==table[path]
for row in run['observations']:
    assert sha(evidence/'observe1'/row['file'])==row['sha256'] and len(row['pairs'])==16
for path,folder,name in [('tools/audit_accel_upper_forward_v1.py','audit1','executed_auditor.py'),
                         ('tools/assess_accel_upper_forward_v1.py','assessment2','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
# Verify every assessment grouping against the actual observations, rather than trusting plotted selections.
for segment in assessment['segments']:
    rows=[v for v in run['observations'] if v['segment']==segment['segment']];assert len(rows)==4
    assert segment['observations']==[dict(branch=v['branch'],pairs=v['pairs']) for v in rows]
assert sum(len(v['pairs']) for v in run['observations'])==assessment['pairs']==192
assert sum(not p['Bernoulli_Gaussian_available'] for v in run['observations'] for p in v['pairs'])==90
for entry,folder in [(first,'assessment1'),(assessment,'assessment2')]:
    for fig in entry['figures']:assert sha(evidence/folder/fig['file'])==fig['sha256']
for fig in assessment['figures']:
    name='research/accel_upper_forward_v1_'+fig['file'];shutil.copy2(evidence/'assessment2'/fig['file'],repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_accel_upper_forward_v1.py','research/高频随机激励前向验证V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs=dict(parent_manifest=parent/'manifest.json',idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json',
            C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voices_path,
            prior_link_manifest=a.workspace/'baselines/accel_upper_link_v1/manifest.json')
validation=dict(schema='vsl.accel-upper-forward-freeze/1',result='native_forward_kernel_verified_pairwise_iid_source_probe_NOT_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='c05dc42 native associations, independent audit with full-MSC limitation retained, complete freeze and clean worktree verified; not wait-only',
    known_controls_before_source=True,all12cases_192pairs_11signedlags=True,
    native_moment_to_rectangular_energy_to_finite_group_operator=True,independent_direct_time_and_matrix_audit=audit,
    assessment_groupings_verified=True,assessment1_color_saturation_preserved=True,assessment2_display_only_change=True,
    final_figures_viewed=True,negative_kappa_preserved_and_unavailable=90,pair_zero_lag_matches_not_validation=True,
    source_PSD_fitted=False,multichannel_fit=False,restricted_iid_white_filter_baseline_only=True,
    source_or_load_or_firing_identity=False,not_confidence_intervals=True,
    new_audio=False,new_profile=False,new_C=False,new_download=False,old_CTests_repeated=False,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    full_MSC_original_gate_still_unpassed=True,original_common_phase_qualification_unwaived=True,
    next=assessment['next'],full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_forward_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_forward_v1','baselines/accel_upper_forward_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'native2/4moment480x480energyfiniteGroup;12cases192pairs11signedlags',
    'zeroLagMatchNOTvoice;90negativeUnavailable;needTemporalPersistence;619C-H67voices',
    'research/高频随机激励前向验证V1.md | research/accel_upper_forward_v1_summary.json','baselines/accel_upper_forward_v1/validation.json'])
print(result)
