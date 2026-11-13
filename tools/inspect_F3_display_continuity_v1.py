"""Decode every F3 candidate frame and conservatively classify only the visible gear overlay."""
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
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from PIL import Image,ImageDraw
from drive_evidence_v1.sources import sha
from F3_display_continuity_v1.mask import orange,classify


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F3-display-continuity/1',result='running',sources={},audio_read=False,
    model_exported=False,runtime_changed=False,physical_shift_timing_established=False)
try:
    plan=load(repo/'research/F3_display_continuity_v1_plan.json')
    catalogue=load(args.workspace/'references/segments_v1.json')
    source=catalogue['sources']['F3'];media=args.workspace/source['video']
    assert sha(media)==source['video_sha256']==source['raw_sha256']
    inspected=load(args.workspace/'references/analysis/state_media_v1/F3_context1/report.json')
    assert inspected['input_sha256']==sha(media)
    time_base=Fraction(inspected['stream']['time_base'])
    rate=Fraction(inspected['stream']['r_frame_rate']);assert rate==60
    report.update(input_sha256=sha(media),source_context_sha256=sha(args.workspace/'references/analysis/state_media_v1/F3_context1/report.json'),
        native_time_base=str(time_base),native_frame_rate=str(rate))
    for path in (Path(__file__),repo/'research/F3_display_continuity_v1_plan.json',
        repo/'tools/F3_display_continuity_v1/__init__.py',repo/'tools/F3_display_continuity_v1/mask.py',
        repo/'tools/drive_evidence_v1/sources.py',repo/'references/segments_v1.json'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    ffmpeg=Path('D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
    x0,y0,x1,y1=plan['roi_xyxy'];width,height=x1-x0,y1-y0
    def decode(name,first,stop,crop=False):
        folder=args.out/name;folder.mkdir()
        p0,p1=int(Fraction(str(first))/time_base),int(Fraction(str(stop))/time_base)
        select="select='gte(pts,"+str(p0)+")*lt(pts,"+str(p1)+")'"
        if crop:
            select+=',format=rgb24,crop='+str(width)+':'+str(height)+':'+str(x0)+':'+str(y0)
        command=[str(ffmpeg),'-hide_banner','-nostdin','-ss',str(first-1),'-copyts','-threads','2','-i',str(media),
            '-an','-vf',select+',showinfo','-frames:v',str(round((stop-first)*float(rate))),
            '-fps_mode','vfr',str(folder/'frame_%04d.png')]
        done=subprocess.run(command,capture_output=True,check=True)
        (folder/'decode_log.txt').write_bytes(done.stderr)
        found=re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',done.stderr.decode('utf-8',errors='replace'))
        rows=[]
        for n,pts,_ in found:
            path=folder/('frame_'+str(int(n)+1).zfill(4)+'.png')
            rows.append(dict(file=path.relative_to(args.out).as_posix(),sha256=sha(path),pts=int(pts),
                source_pts_seconds=float(int(pts)*time_base)))
        assert len(rows)==round((stop-first)*float(rate))
        frame_indices=[round((row['source_pts_seconds']-first)*float(rate)) for row in rows]
        assert frame_indices==list(range(len(rows)))
        assert all(p0<=row['pts']<p1 for row in rows)
        return dict(command=command,frames=rows,all_native_timing_indices_contiguous=True)
    templates={};references=[]
    for gear,second in plan['template_video_seconds'].items():
        captured=decode('template_'+gear,second,second+1/60)
        row=captured['frames'][0]
        with Image.open(args.out/row['file']) as picture:
            templates[gear]=orange(picture.convert('RGB').crop((x0,y0,x1,y1)))
        references.append(dict(gear=int(gear),capture=captured))
    controls=[]
    for gear,second in plan['independent_probe_video_seconds'].items():
        captured=decode('probe_'+gear,second,second+1/60)
        with Image.open(args.out/captured['frames'][0]['file']) as picture:
            mask=orange(picture.convert('RGB').crop((x0,y0,x1,y1)))
        observed=classify(mask,templates)
        controls.append(dict(id='independent_gear_'+gear,expected=int(gear),observed=observed,
            passed=observed['displayed_gear']==int(gear),capture=captured))
    for name,mask in [('blank',np.zeros_like(templates['4'])),('union_4_5',templates['4']|templates['5'])]:
        observed=classify(mask,templates)
        controls.append(dict(id=name,expected=None,observed=observed,passed=observed['displayed_gear'] is None))
    scalar_error=0.
    for left in templates.values():
        for key,right in templates.items():
            scalar=2*sum(bool(a and b) for a,b in zip(left.ravel(),right.ravel()))/(
                sum(bool(a) for a in left.ravel())+sum(bool(b) for b in right.ravel()))
            scalar_error=max(scalar_error,abs(scalar-classify(left,templates)['all_Dice'][key]))
    assert scalar_error<=1e-12
    report.update(templates=references,controls=controls,detector_controls_passed=all(row['passed'] for row in controls),
        scalar_Dice_error=scalar_error)
    save(args.out/'controls.json',dict(controls=controls,passed=report['detector_controls_passed'],scalar_Dice_error=scalar_error))
    # Even failed controls are retained; no gate change or forced label follows.
    windows={}
    for window in plan['windows']:
        captured=decode(window['id'],*window['seconds'],crop=True)
        rows=[]
        for row in captured['frames']:
            with Image.open(args.out/row['file']) as picture:
                observed=classify(orange(picture.convert('RGB')),templates)
            rows.append(dict(**row,**observed))
        captured['frames']=rows;windows[window['id']]=captured
        # Review every unknown plus representative boundary/worst matches, without changing labels.
        selected={0,len(rows)-1}
        selected.update(i for i,row in enumerate(rows) if row['displayed_gear'] is None)
        selected.update(i for i in range(1,len(rows)) if rows[i]['displayed_gear']!=rows[i-1]['displayed_gear'])
        selected.update(sorted(range(len(rows)),key=lambda i:rows[i]['best_Dice'])[:12])
        chosen=[rows[i] for i in sorted(selected)]
        sheet=Image.new('RGB',(6*(width+8),math.ceil(len(chosen)/6)*(height+38)),'#151b22')
        draw=ImageDraw.Draw(sheet)
        for i,row in enumerate(chosen):
            x,y=i%6*(width+8),i//6*(height+38)
            with Image.open(args.out/row['file']) as picture:sheet.paste(picture,(x,y))
            draw.text((x+2,y+height+2),str(row['source_pts_seconds'])+'s G'+str(row['displayed_gear']),fill='white')
            draw.text((x+2,y+height+16),'Dice '+format(row['best_Dice'],'.4f'),fill='white')
        sheet.save(args.out/(window['id']+'_review.png'))
        captured['review_sheet_sha256']=sha(args.out/(window['id']+'_review.png'))
        captured['review_frames']=[row['file'] for row in chosen]
        print(json.dumps(dict(window=window['id'],frames=len(rows),unknown=sum(row['displayed_gear'] is None for row in rows))),flush=True)
    candidates=[]
    for candidate in plan['candidate_intervals']:
        first,stop=candidate['seconds']
        rows=[row for value in windows.values() for row in value['frames'] if first<=row['source_pts_seconds']<stop]
        assert len(rows)==round((stop-first)*float(rate))
        candidates.append(dict(**candidate,frames=len(rows),unknown_frames=sum(row['displayed_gear'] is None for row in rows),
            all_frames_match_displayed_gear=all(row['displayed_gear']==candidate['displayed_gear'] for row in rows)))
    report.update(result='native_frame_display_evidence_measured' if report['detector_controls_passed'] else
        'native_frames_retained_detector_not_qualified',windows=windows,candidates=candidates,
        limits=['Overlay image classification, not physical gearbox telemetry or independently synchronized sound',
            'Native timing coverage does not prove source images unedited or recordings independent',
            'Unknown frames retained; failed controls invalidate detector-based continuous-state claims'])
    print(json.dumps(dict(result=report['result'],candidates=candidates)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    save(args.out/'report.json',report)
