"""Test one-pixel outline evidence on saved native frames, preserving rejected Dice detector."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--parent',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from PIL import Image,ImageDraw
from drive_evidence_v1.sources import sha
from F3_display_continuity_v1.mask import orange
from F3_display_continuity_v1.shape import classify


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F3-display-shape/1',result='running',sources={},audio_read=False,
    model_exported=False,runtime_changed=False,physical_shift_timing_established=False)
try:
    parent=load(args.parent/'report.json')
    assert parent['result']=='native_frames_retained_detector_not_qualified'
    assert not parent['detector_controls_passed']
    plan=load(repo/'research/F3_display_shape_v1_plan.json')
    original=load(repo/'research/F3_display_continuity_v1_plan.json')
    catalogue=load(args.workspace/'references/segments_v1.json')
    media=args.workspace/catalogue['sources']['F3']['video']
    assert sha(media)==parent['input_sha256']
    for path in (Path(__file__),repo/'research/F3_display_shape_v1_plan.json',
        repo/'research/F3_display_continuity_v1_plan.json',repo/'tools/F3_display_continuity_v1/mask.py',
        repo/'tools/F3_display_continuity_v1/shape.py',repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    def mask_at(root,row,crop=False):
        path=root/row['file'];assert sha(path)==row['sha256']
        with Image.open(path) as picture:
            picture=picture.convert('RGB')
            if crop:picture=picture.crop(tuple(original['roi_xyxy']))
            return orange(picture)
    templates={str(row['gear']):mask_at(args.parent,row['capture']['frames'][0],True) for row in parent['templates']}
    controls=[]
    for row in parent['controls']:
        if 'capture' not in row:continue
        observed=classify(mask_at(args.parent,row['capture']['frames'][0],True),templates)
        controls.append(dict(id='regression_'+row['id'],expected=row['expected'],observed=observed,
            passed=observed['displayed_gear']==row['expected'],source_capture=row['capture']))
    probe_captures=[]
    ffmpeg=Path('D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
    for gear,second in plan['new_probe_video_seconds'].items():
        folder=args.out/('probe_'+gear);folder.mkdir()
        command=[str(ffmpeg),'-hide_banner','-nostdin','-ss',str(second-1),'-copyts','-threads','2','-i',str(media),
            '-an','-vf',"select='eq(pts,"+str(second*1000)+")',showinfo",'-frames:v','1','-fps_mode','vfr',str(folder/'frame.png')]
        done=subprocess.run(command,capture_output=True,check=True);(folder/'decode_log.txt').write_bytes(done.stderr)
        found=re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',done.stderr.decode('utf-8',errors='replace'))
        assert len(found)==1 and int(found[0][1])==second*1000
        row=dict(file=(folder/'frame.png').relative_to(args.out).as_posix(),sha256=sha(folder/'frame.png'),pts=second*1000,
                 source_pts_seconds=second)
        observed=classify(mask_at(args.out,row,True),templates)
        capture=dict(gear=int(gear),frame=row,command=command);probe_captures.append(capture)
        controls.append(dict(id='new_native_probe_'+gear,expected=int(gear),observed=observed,
            passed=observed['displayed_gear']==int(gear)))
    corrupted=templates['5'].copy();corrupted[:corrupted.shape[0]//2]=False
    shifted=np.zeros_like(templates['5']);shifted[:,1:]=templates['5'][:,:-1]
    for name,mask,expected in [('blank',np.zeros_like(shifted),None),('union_4_5',templates['4']|templates['5'],None),
        ('half_outline_missing',corrupted,None),('one_pixel_shift',shifted,5)]:
        observed=classify(mask,templates)
        controls.append(dict(id=name,expected=expected,observed=observed,passed=observed['displayed_gear']==expected))
    passed=all(row['passed'] for row in controls)
    report.update(parent_report_sha256=sha(args.parent/'report.json'),new_probe_captures=probe_captures,
        controls=controls,detector_controls_passed=passed)
    save(args.out/'controls.json',dict(passed=passed,controls=controls))
    windows={}
    for name,value in parent['windows'].items():
        rows=[dict(**{key:row[key] for key in ('file','sha256','pts','source_pts_seconds')},
                   **classify(mask_at(args.parent,row),templates)) for row in value['frames']]
        windows[name]=dict(frames=rows,original_timing_coverage_unchanged=True)
        chosen=set((0,len(rows)-1))
        chosen.update(i for i,row in enumerate(rows) if row['displayed_gear'] is None)
        chosen.update(i for i in range(1,len(rows)) if rows[i]['displayed_gear']!=rows[i-1]['displayed_gear'])
        chosen.update(sorted(range(len(rows)),key=lambda i:rows[i]['best_shape_score'])[:12])
        selected=[rows[i] for i in sorted(chosen)]
        sheets=[]
        for start in range(0,len(selected),36):
            part=selected[start:start+36];sheet=Image.new('RGB',(6*183,math.ceil(len(part)/6)*246),'#151b22');draw=ImageDraw.Draw(sheet)
            for i,row in enumerate(part):
                x,y=i%6*183,i//6*246
                with Image.open(args.parent/row['file']) as picture:sheet.paste(picture,(x,y))
                draw.text((x+2,y+209),str(row['source_pts_seconds'])+'s G'+str(row['displayed_gear']),fill='white')
                draw.text((x+2,y+224),'shape '+format(row['best_shape_score'],'.4f'),fill='white')
            filename=name+'_review_'+str(start//36+1)+'.png';sheet.save(args.out/filename)
            sheets.append(dict(file=filename,sha256=sha(args.out/filename),frames=[row['file'] for row in part]))
        windows[name]['review_sheets']=sheets
    candidates=[]
    for candidate in original['candidate_intervals']:
        a,b=candidate['seconds'];rows=[row for value in windows.values() for row in value['frames'] if a<=row['source_pts_seconds']<b]
        assert len(rows)==(b-a)*60
        candidates.append(dict(**candidate,frames=len(rows),unknown_frames=sum(row['displayed_gear'] is None for row in rows),
            all_frames_match_displayed_gear=all(row['displayed_gear']==candidate['displayed_gear'] for row in rows)))
    report.update(result='native_outline_evidence_measured' if passed else 'native_outline_detector_not_qualified',
        windows=windows,candidates=candidates,
        limits=['One-pixel engineering raster tolerance and limited image controls, not a general OCR guarantee',
            'Every unknown retained; failed controls forbid detector-based continuous display claims',
            'Overlay timing is not physical shift, calibrated audio timing, RPM, load or fueling'])
    print(json.dumps(dict(result=report['result'],controls=[dict(id=row['id'],passed=row['passed']) for row in controls],candidates=candidates)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',report)
