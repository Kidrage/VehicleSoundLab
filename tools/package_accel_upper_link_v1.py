"""Freeze all source associations, including the failed all-bin MSC qualification."""
import argparse,csv,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/accel_upper_link_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/accel_upper_link_v1'
run=load(evidence/'observe1/report.json');failed=load(evidence/'audit1/report.json')
audit=load(evidence/'audit2/report.json');assessment=load(evidence/'assessment1/report.json')
assert run['result']=='all12_low_to_upper_power_associations_observed' and run['native_windows']==900
assert failed['result']=='failed' and 'every_bin_MSC' in failed['error']
assert audit['result']=='native_and_summaries_passed_full_MSC_tolerance_not_passed'
assert audit['observations']==12 and audit['windows']==900 and audit['cross_spectra']==96 and audit['band_summaries']==48
assert len(audit['full_MSC_tolerance_failures'])==12 and not audit['full_MSC_independent_tolerance_passed']
assert audit['fixed_30_to600Hz_summaries_passed'] and audit['original_full_MSC_gate_unchanged']==2e-8
assert assessment['result']=='fixed_band_associations_assessed_full_MSC_gate_unpassed'
assert failed['input_sha256']==audit['input_sha256']==assessment['input_sha256']==sha(evidence/'observe1/report.json')
assert assessment['audit_sha256']==sha(evidence/'audit2/report.json')
sources=set(run['sources'])
for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(evidence/'observe1/exact_sources'/path)
parent=a.workspace/'baselines/accel_upper_joint_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
for path,digest in run['parent_files'].items():assert sha(parent/path)==digest==table[path]
for row in run['observations']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for path,folder,name in [('tools/audit_accel_upper_link_v1.py','audit2','executed_auditor.py'),
                         ('tools/assess_accel_upper_link_v1.py','assessment1','executed_assessment.py')]:
    assert sha(repo/path)==sha(evidence/folder/name);sources.add(path)
# Independently recompute every assessment grouping and the complete source/control comparison count.
above=0;count=0
for segment in assessment['segments']:
    source=next(v for v in run['observations'] if v['segment']==segment['segment'] and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment['segment'] and v['branch']!='original']
    assert segment['windows']==source['windows'] and len(segment['bands'])==4 and len(controls)==3
    for b,item in enumerate(segment['bands']):
        assert item['original']==source['summary'][b] and item['band_hz']==source['summary'][b]['band_hz']
        assert item['controls']==[dict(branch=v['branch'],summary=v['summary'][b]) for v in controls]
        for i in range(2):
            for j in range(4):
                values=[v['summary'][b]['power_weighted_MSC'][i][j] for v in controls]
                value=source['summary'][b]['power_weighted_MSC'][i][j]
                assert item['control_min'][i][j]==min(values) and item['control_max'][i][j]==max(values)
                assert item['original_minus_control_max'][i][j]==value-max(values)
                assert item['original_above_all_three'][i][j]==(value>max(values))
                if i==j%2:count+=1;above+=int(value>max(values))
assert count==assessment['same_channel_cases']==48 and above==assessment['same_channel_above_all_controls']==25
for fig in assessment['figures']:
    path=evidence/'assessment1'/fig['file'];assert sha(path)==fig['sha256']
    name='research/accel_upper_link_v1_'+fig['file'];shutil.copy2(path,repo/name);sources.add(name)
ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json';voices=load(voices_path)
assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
sources.update(['tools/package_accel_upper_link_v1.py','research/加速高低频关联V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs=dict(parent_manifest=parent/'manifest.json',idle_pending_manifest=a.workspace/'baselines/idle_complex75_v1/manifest.json',
            C_H_index=repo/'handoff/C文件索引.csv',voice_hashes=voices_path)
validation=dict(schema='vsl.accel-upper-link-freeze/1',result='fixed_band_associations_verified_full_MSC_qualification_not_passed_NO_voice',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    previous_goal_turn_progress='8d5ebcb all source joint covariance/fourth moments, complete native independent audit, figures and exact archive; not a wait-only turn',
    all3original_plus9phase_controls=True,all_native2401bins=True,all8signed_complex_cross_spectra=True,
    known_AM_Gaussian_and_beating_counterexample_before_source=True,independent_native_features=True,
    all_fixed48band_summaries_verified=True,all_bin_MSC_gate_unpassed=True,
    original_all_bin_MSC_gate_unchanged=2e-8,failed_audit1=failed,complete_audit2=audit,
    failure_and_source_arrays_preserved=True,assessment_groupings_independently_verified=True,
    old_phase_PSD_LR_CSD_audit_hash_reused_not_rerun=True,figures_viewed=True,
    uniform_low_driven_upper_AM_justified=False,cyclic_coupling_absence_proven=False,source_identity=False,
    same_recording_overlapping_windows_not_confidence_intervals=True,new_audio=False,new_profile=False,new_C=False,
    new_download=False,old_CTests_repeated=False,old619C_H_and67voices_exact=True,
    moving35_changed=False,runtime_changed=False,pending_idle_listening_unchanged=True,
    next=assessment['next'],original_common_phase_qualification_unwaived=True,full_goal_complete=False)
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/accel_upper_link_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['accel_upper_link_v1','baselines/accel_upper_link_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '12native2401bins900windows;2x4CSD;48fixedband;FULL-MSCgateNOTpassed',
    '25of48above3controlsNOTclock;beatingCounter;619C-H67voices;NOaudio/C',
    'research/加速高低频关联V1.md | research/accel_upper_link_v1_summary.json','baselines/accel_upper_link_v1/validation.json'])
print(result)
