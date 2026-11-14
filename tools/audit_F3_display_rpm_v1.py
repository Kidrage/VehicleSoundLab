"""Audit image/PTS/annotation bindings; never certify visual RPM truth from hashes."""
import argparse,csv,re,shutil,sys
from fractions import Fraction
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from PIL import Image
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_auditor.py')
report=dict(schema='vsl.F3-display-rpm-audit/1',result='running',
    image_PTS_bindings_verified=False,manual_RPM_truth_independently_verified=False,
    audio_read=False,runtime_changed=False)
try:
    images=load(a.input/'report.json')
    annotation_path=repo/'research/F3_display_rpm_v1_annotations.json';annotation=load(annotation_path)
    plan_path=repo/'research/F3_display_rpm_v1_plan.json';plan=load(plan_path)
    shutil.copy2(annotation_path,a.out/'annotations.json')
    assert images['plan_sha256']==sha(plan_path)
    assert sha(a.input/'parent_report.json')==images['parent_report_sha256']
    parent=load(a.input/'parent_report.json');time_base=Fraction(parent['stream']['time_base'])
    fetch=load(a.input/'fetch_report.json')
    assert sha(a.workspace/fetch['file'])==fetch['sha256']==images['media_sha256']
    assert images['result']=='native_display_samples_prepared_for_manual_reading'
    assert len(images['frames'])==len(annotation['rows'])==20
    assert sorted(t for times in plan['samples_seconds'].values() for t in times)==[row[0] for row in annotation['rows']]
    checked=[]
    for image,note in zip(images['frames'],annotation['rows']):
        second,gear,speed,lower,upper,_=note
        assert image['seconds']==second and Fraction(image['pts'])*time_base==second
        assert 1<=gear<=7 and speed>0 and 0<=lower<upper<=10000 and lower%1000==upper%1000==0
        assert image['crop_xyxy']==plan['crop_xyxy']
        original=a.workspace/image['parent_file'];full=a.input/image['full'];crop=a.input/image['crop']
        assert sha(original)==sha(full)==image['parent_sha256']==image['full_sha256']
        assert sha(crop)==image['crop_sha256']
        old=parent['observations'][image['scene']]
        matching=[v for v in old['frames'] if v['pts']==image['pts']]
        assert len(matching)==1 and matching[0]['sha256']==sha(original)
        original_n=int(Path(matching[0]['file']).stem.rsplit('_',1)[1])-1
        log=a.input/image['decode_log'];assert sha(log)==image['decode_log_sha256']
        parsed=[(int(n),int(pts)) for n,pts in re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+)',log.read_text(encoding='utf-8',errors='replace'))]
        assert (original_n,image['pts']) in parsed
        with Image.open(full) as frame:expected=np.asarray(frame.convert('RGB'))
        with Image.open(crop) as picture:observed=np.asarray(picture.convert('RGB'))
        x0,y0,x1,y1=plan['crop_xyxy']
        assert np.array_equal(expected[y0:y1,x0:x1,:],observed)
        checked.append(dict(seconds=second,pts=image['pts'],all_crop_RGB_exact=True,
            original_file_sha256=sha(original),displayed_gear=gear,displayed_speed_kmh=speed,
            coarse_RPM_range=[lower,upper],manual_visual_truth_audited=False))
    for row in images['sheets']:assert sha(a.input/row['file'])==row['sha256']
    ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
    assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
    voices_path=a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json'
    voices=load(voices_path)
    assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
    # No interpolation or learned audio-state model is produced by this study.
    assert not annotation['physical_RPM_calibrated'] and not annotation['audio_video_delay_calibrated']
    assert not annotation['interpolated_RPM_trajectory_exported'] and not annotation['manual_reading_independently_verified']
    report.update(result='passed',image_PTS_bindings_verified=True,all20_RGB_crops_exact=True,
        checked=checked,original619C_H_and67voices_exact=True,
        annotations_sha256=sha(annotation_path),image_report_sha256=sha(a.input/'report.json'),
        note='Pass concerns source identity, image operations, PTS and table bindings. Manual needle interpretation is not independently validated; no audio was read, fitted or generated.')
finally:save(a.out/'report.json',report)
print(dict(result=report['result'],frames=len(report.get('checked',[]))))
