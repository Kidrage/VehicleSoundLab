"""Prepare native image evidence for coarse manual display-RPM annotations."""
import argparse
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image,ImageDraw,ImageFont
from research_archive_v1 import load,save,sha

a.out.resolve().relative_to((a.workspace/'references/analysis/F3_display_rpm_v1').resolve())
a.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/F3_display_rpm_v1_plan.json';plan=load(plan_path)
parent=a.workspace/'references/analysis/state_media_v1/F3_context1'
prior=load(parent/'report.json')
fetch_path=a.workspace/'references/raw/state_media_v1/F3_fetch2/report.json';fetch=load(fetch_path)
media=a.workspace/fetch['file']
assert sha(media)==fetch['sha256']==prior['input_sha256']
report=dict(schema='vsl.F3-display-rpm-images/1',result='running',
    plan_sha256=sha(plan_path),parent_report_sha256=sha(parent/'report.json'),
    media_sha256=sha(media),frames=[],sheets=[],audio_read=False,
    runtime_changed=False,automatic_RPM_detector_used=False,manual_annotations_completed=False)
for file in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py']:
    dest=a.out/'exact_sources'/file.relative_to(repo)
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
shutil.copy2(parent/'report.json',a.out/'parent_report.json')
shutil.copy2(fetch_path,a.out/'fetch_report.json')
try:
    bounds=tuple(plan['crop_xyxy'])
    for scene,times in plan['samples_seconds'].items():
        observation=prior['observations'][scene]
        log=parent/scene/'frame_log.txt'
        shutil.copy2(log,a.out/(scene+'_decode_log.txt'))
        for second in times:
            found=[row for row in observation['frames'] if row['source_pts_seconds']==second]
            assert len(found)==1
            row=found[0];source=parent/scene/row['file']
            assert sha(source)==row['sha256']
            name=scene+'_'+str(second)
            original=a.out/(name+'_full.jpg');shutil.copy2(source,original)
            with Image.open(source) as picture:
                assert picture.size==(1920,1080)
                crop=picture.convert('RGB').crop(bounds)
            dest=a.out/(name+'_crop.png');crop.save(dest)
            report['frames'].append(dict(scene=scene,seconds=second,pts=row['pts'],
                parent_file=source.relative_to(a.workspace).as_posix(),parent_sha256=row['sha256'],
                full=original.name,full_sha256=sha(original),crop=dest.name,crop_sha256=sha(dest),
                crop_xyxy=list(bounds),decode_log=scene+'_decode_log.txt',decode_log_sha256=sha(log)))
    # Two native-size columns; no image resampling. Labels occupy their own strip.
    width,height=bounds[2]-bounds[0],bounds[3]-bounds[1]
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',20)
    for first in range(0,len(report['frames']),6):
        rows=report['frames'][first:first+6]
        board=Image.new('RGB',(2*width,((len(rows)+1)//2)*(height+32)), '#101922')
        draw=ImageDraw.Draw(board)
        for i,row in enumerate(rows):
            x,y=i%2*width,i//2*(height+32)
            with Image.open(a.out/row['crop']) as crop:board.paste(crop,(x,y))
            draw.text((x+8,y+height+4),str(row['seconds'])+' s | native JPEG crop | PTS '+str(row['pts']),font=font,fill='white')
        dest=a.out/('sheet_'+str(first//6+1).zfill(2)+'.png');board.save(dest)
        report['sheets'].append(dict(file=dest.name,sha256=sha(dest)))
    report['result']='native_display_samples_prepared_for_manual_reading'
finally:
    save(a.out/'report.json',report)
print(dict(result=report['result'],frames=len(report['frames']),sheets=len(report['sheets'])))
