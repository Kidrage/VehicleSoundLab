"""Freeze complete F3 shared/independent upper temporal evidence without promoting a voice."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_upper_joint_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_joint_v1'
run=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_joint_upper_observations_complete' and len(run['observations'])==12
assert sum(v['tiles'] for v in run['observations'])==192
assert audit['result']=='passed' and audit['observations']==12 and audit['tile_moments']==192 and audit['phase_controls']==9
assert assessment['result']=='all_joint_upper_groups_assessed'
assert audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit1/report.json')
sources=set(run['sources'])
for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path)
parent=a.workspace/'baselines/accel_upper_inventory_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
for path,digest in run['parent_files'].items():assert sha(parent/path)==digest
for row in run['observations']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_accel_upper_joint_v1.py','audit1','executed_auditor.py'),('tools/assess_accel_upper_joint_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
for segment in assessment['segments']:
    assert len(segment['pairs'])==6
    original=next(v for v in run['observations'] if v['segment']==segment['segment'] and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment['segment'] and v['branch']!='original']
    for pair in segment['pairs']:
        i,j=pair['indices'];assert pair['total']==original['energy']['normalized_total'][i][j]
        assert pair['within']==original['energy']['normalized_within'][i][j] and pair['between']==original['energy']['normalized_between'][i][j]
        for key,values in pair['phase_controls'].items():
            expected=[v['energy'][key][i][j] for v in controls];assert values['values']==expected and values['range']==[min(expected),max(expected)]
fig=assessment['figure'];assert sha(evidence/'assessment1'/fig['file'])==fig['sha256']
shutil.copy2(evidence/'assessment1'/fig['file'],repo/'research/accel_upper_joint_v1.png');sources.add('research/accel_upper_joint_v1.png')
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')));assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_accel_upper_joint_v1.py','research/加速高频共同细节V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs=dict(parent_manifest=parent/'manifest.json',idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json',C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voices_path)
validation=dict(schema='vsl.accel-upper-joint-freeze/1',result='all3_F3_slow_and_fast_joint_upper_structure_measured_NO_audio_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='f4fd313 source-derived native complex75 candidate, all audio/observer audits, page and exact freeze; clean worktree verified',
    all3original_plus9phase_controls=True,all48original_tiles_4conditions=True,native_tile_moments=192,
    correlated_Gaussian_and_shared_independent_scale_controls=True,all4x4signed_covariances=True,all11signed_lags=True,
    exact_weighted_within_between_partition=True,independent_frequency_filter_and_scalar_moment_audit=True,
    audit=audit,segments=assessment['segments'],figure_viewed=True,source_physical_identity=False,
    apparent_fast_or_slow_not_proven_mechanical_or_load=True,not_independent_recordings_or_confidence_intervals=True,
    new_audio=False,new_profile=False,new_C=False,new_download=False,old_CTests_repeated=False,
    old619C_H_and67voices_exact=True,moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    next=assessment['next'],original_common_phase_qualification_unwaived=True,full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_joint_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_joint_v1','baselines/accel_upper_joint_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '12fullpassages192tiles;4x4signed4th/cov;11lags;independentFFT/moments',
    'slow+fastHFdependence;stereoDistinct;NOvoice/C/promotion;619C-H67voices',
    'research/加速高频共同细节V1.md | research/accel_upper_joint_v1_summary.json','baselines/accel_upper_joint_v1/validation.json'])
print(result)
