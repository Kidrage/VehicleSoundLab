"""Read approved A's existing partial HD stream without claiming full download."""
import argparse,json,re,shutil,subprocess,sys
from fractions import Fraction
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image,ImageDraw,ImageFont
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
source=a.workspace/'references/analysis/A_hires_v1/fetch1/A_picture.mp4.part'
fetch=source.parent/'report.json';approval=a.workspace/'references/approval_manifest.json'
record=next(x for x in json.loads(approval.read_text(encoding='utf-8')) if x['id']=='A')
assert record['approved'] and record['video_id']=='7aZm1Wkp6QM'
r=dict(schema='vsl.A-startup-HD-observation/1',result='running',source=str(source),
       whole_download_completed=False,source_sha256=sha(source),fetch_report_sha256=sha(fetch),
       approval_manifest_sha256=sha(approval),source_code_sha256=sha(__file__),
       limits=['Original decoded picture PTS, not ECU timestamps or independently measured A/V alignment',
               'Incomplete whole source retained; only the decoded local interval is asserted usable',
               'Native crop and display-only resize; no enhancement, OCR or synthesized instrument readings'])
shutil.copy2(__file__,a.out/'executed_observe.py')
try:
    command=['ffprobe','-v','error','-select_streams','v:0','-read_intervals','0%40.7',
             '-show_frames','-show_entries','stream=width,height,time_base,avg_frame_rate:frame=best_effort_timestamp',
             '-of','json',str(source)]
    done=subprocess.run(command,capture_output=True,timeout=60)
    (a.out/'frame_index.json').write_bytes(done.stdout);(a.out/'index_errors.log').write_bytes(done.stderr)
    assert done.returncode==0
    index=json.loads(done.stdout);stream=index['streams'][0]
    assert (stream['width'],stream['height'])==(1920,1080)
    base=Fraction(stream['time_base']);by_pts={int(v['best_effort_timestamp']):i for i,v in enumerate(index['frames'])}
    select='between(t,35.5,40.5)*not(mod(n,6))'
    command=['ffmpeg','-v','info','-nostdin','-n','-to','40.6','-i',str(source),
             '-vf',f"select='{select}',crop=440:280:600:240,showinfo",'-fps_mode','vfr',str(a.out/'frame_%03d.png')]
    done=subprocess.run(command,capture_output=True,timeout=60)
    (a.out/'decode.log').write_bytes(done.stderr);assert done.returncode==0
    parsed=re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)',done.stderr.decode(errors='replace'))
    rows=[]
    for number,pts,shown in parsed:
        pts=int(pts);seconds=float(pts*base);assert abs(seconds-float(shown))<.001
        path=a.out/f'frame_{int(number)+1:03d}.png';assert Image.open(path).size==(440,280)
        rows.append(dict(file=path.name,pts=pts,source_frame_index=by_pts[pts],source_seconds=seconds,sha256=sha(path)))
    assert len(rows)==len(list(a.out.glob('frame_*.png'))) and len(rows)>=45
    assert rows[0]['source_seconds']<35.7 and rows[-1]['source_seconds']>40.3
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',18);sheets=[]
    for start in range(0,len(rows),12):
        subset=rows[start:start+12];board=Image.new('RGB',(1320,310*((len(subset)+2)//3)),'#101922');draw=ImageDraw.Draw(board)
        for i,row in enumerate(subset):
            x=i%3*440;y=i//3*310
            board.paste(Image.open(a.out/row['file']),(x,y));draw.text((x+8,y+282),f"{row['source_seconds']:.3f}s | #{row['source_frame_index']}",font=font,fill='white')
        path=a.out/f'sheet_{start//12+1:02d}.png';board.save(path);sheets.append(path.name)
    r.update(result='HD_local_startup_frames_decoded',time_base=str(base),frame_index_sha256=sha(a.out/'frame_index.json'),
             crop=[600,240,440,280],selection=select,decoded_frames=rows,sheets=sheets,exact_RPM_annotated=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],frames=len(r.get('decoded_frames',[])),sheets=r.get('sheets',[]))))
