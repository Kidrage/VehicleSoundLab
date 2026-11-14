"""Freeze coarse visual evidence without treating manual reads as measured telemetry."""
import argparse,shutil,subprocess,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha,freeze,verify,append_index

root=a.workspace/'baselines/F3_display_rpm_v1'
if a.stage=='verify':print(verify(root)['file_count']);raise SystemExit
evidence=a.workspace/'references/analysis/F3_display_rpm_v1'
images=load(evidence/'inspect1/report.json');audit=load(evidence/'audit1/report.json')
assert images['result']=='native_display_samples_prepared_for_manual_reading'
assert audit['result']=='passed' and audit['all20_RGB_crops_exact'] and len(audit['checked'])==20
assert not audit['manual_RPM_truth_independently_verified'] and audit['original619C_H_and67voices_exact']
assert audit['image_report_sha256']==sha(evidence/'inspect1/report.json')
assert audit['annotations_sha256']==sha(repo/'research/F3_display_rpm_v1_annotations.json')
assert sha(evidence/'audit1/executed_auditor.py')==sha(repo/'tools/audit_F3_display_rpm_v1.py')
assert sha(evidence/'audit1/annotations.json')==sha(repo/'research/F3_display_rpm_v1_annotations.json')
for name in ['tools/inspect_F3_display_rpm_v1.py','tools/research_archive_v1.py','research/F3_display_rpm_v1_plan.json']:
    assert sha(evidence/'inspect1/exact_sources'/name)==sha(repo/name)
for row in images['frames']:
    assert sha(evidence/'inspect1'/row['full'])==row['full_sha256']
    assert sha(evidence/'inspect1'/row['crop'])==row['crop_sha256']
for row in images['sheets']:assert sha(evidence/'inspect1'/row['file'])==row['sha256']
sources=['tools/inspect_F3_display_rpm_v1.py','tools/audit_F3_display_rpm_v1.py',
    'tools/package_F3_display_rpm_v1.py','tools/research_archive_v1.py',
    'research/F3_display_rpm_v1_plan.json','research/F3_display_rpm_v1_annotations.json',
    'research/F3画面转速范围V1.md','AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md']
shutil.copy2(repo/'AGENTS.md',a.workspace/'AGENTS.md')
inputs={'C_H_index.csv':repo/'handoff/C文件索引.csv',
    'voice_files_sha256.json':a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json',
    'prior_F3_context_report.json':a.workspace/'references/analysis/state_media_v1/F3_context1/report.json',
    'prior_gear_shape_report.json':a.workspace/'references/analysis/F3_display_continuity_v1/shape1/report.json'}
validation=dict(schema='vsl.F3-display-rpm-freeze/1',result='coarse_manual_display_context_NOT_audio_or_runtime',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    original_video_sha256=images['media_sha256'],native_JPEG_source=True,additional_crop_resampling=False,
    sampled_frames=20,all4native_contact_sheets_viewed=True,all20_RGB_and_PTS_bindings_audited=True,
    all619C_H_and67voices_exact=True,manual_RPM_truth_independently_verified=False,
    physical_RPM_or_audio_video_delay_calibrated=False,interpolated_trajectory_exported=False,
    audio_read=False,audio_generated=False,runtime_changed=False,moving35_changed=False,
    latest_idle_candidate='idle_local_partition_v1/review1; remains pending hearing, not C/default',
    next='Hear idle allocation before C. Use F3 brackets only as coarse display context, never transfer to F2 idle. Preserve phase qualifications/full state/multi-engine/7.1.4 goal.')
result=freeze(root,repo,sources,evidence,inputs,validation);verify(root)
save(repo/'research/F3_display_rpm_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['F3_display_rpm_v1','baselines/F3_display_rpm_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],'20nativeJPEGcrops/PTSbindings;4sheetsviewed;619C-H67voicesexact',
    'coarsemanualRPMnotindependentlyverified;noAVcalibration/audio/C',
    'research/F3画面转速范围V1.md | research/F3_display_rpm_v1_summary.json','baselines/F3_display_rpm_v1/validation.json'])
print(result)
