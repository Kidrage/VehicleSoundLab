"""Inspect approved low-speed context with exact decoded frame PTS."""
import argparse,json,re,shutil,subprocess,sys
from fractions import Fraction
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--plan',type=Path)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image,ImageDraw,ImageFont
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-context-inspection/1',result='running',sources={},source_sha256=sha(Path(__file__)))
try:
    catalog_path=repo/'references/segments_v1.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    r['catalog_sha256']=sha(catalog_path)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',17)
    cases={'A':dict(ranges=[[204,211],[241,247.5]],step=1),
           'D':dict(ranges=[[0,18]],step=3),'E':dict(ranges=[[0,21]],step=3)}
    if a.plan:
        cases=json.loads(a.plan.read_text(encoding='utf-8'))
        r['inspection_plan_sha256']=sha(a.plan);shutil.copy2(a.plan,a.out/'executed_plan.json')
    for source,case in cases.items():
        entry=catalog['sources'][source];video=a.workspace/entry['video']
        assert sha(video)==entry['video_sha256']
        output=a.out/source;output.mkdir()
        stream=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=time_base,r_frame_rate,width,height','-of','json',str(video)]))['streams'][0]
        stride=round(float(Fraction(stream['r_frame_rate']))*case['step'])
        selection='+'.join(f'between(t,{lo},{hi})' for lo,hi in case['ranges'])
        command=['ffmpeg','-nostdin','-n','-v','info','-to',str(max(v[1] for v in case['ranges'])+.1),
            '-i',str(video),'-vf',f"select='({selection})*not(mod(n,{stride}))',showinfo",
            '-fps_mode','vfr',str(output/'frame_%03d.png')]
        done=subprocess.run(command,capture_output=True,timeout=60)
        (output/'decode.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
        parsed=re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',done.stderr.decode('utf-8',errors='replace'))
        rows=[];base=Fraction(stream['time_base'])
        for number,pts,shown in parsed:
            file=output/f'frame_{int(number)+1:03d}.png';seconds=float(int(pts)*base)
            assert abs(seconds-float(shown))<.001
            rows.append(dict(file=file.name,pts=int(pts),source_seconds=seconds,sha256=sha(file)))
        assert rows and len(rows)==len(list(output.glob('frame_*.png')))
        boards=[]
        for first in range(0,len(rows),8):
            subset=rows[first:first+8];board=Image.new('RGB',(1280,390*((len(subset)+1)//2)),'#13202a')
            draw=ImageDraw.Draw(board)
            for i,row in enumerate(subset):
                with Image.open(output/row['file']) as frame:
                    frame=frame.convert('RGB');frame.thumbnail((640,360))
                    x,y=i%2*640,i//2*390;board.paste(frame,(x,y))
                    draw.text((x+8,y+363),f"{source} | PTS {row['source_seconds']:.6f}s",font=font,fill='white')
            file=output/f'board_{first//8+1}.jpg';board.save(file,quality=94)
            boards.append(dict(file=file.name,sha256=sha(file)))
        r['sources'][source]=dict(video=str(video),video_sha256=sha(video),approval=entry['approval'],
            stream=stream,command=command,frames=rows,boards=boards)
        print(json.dumps(dict(source=source,frames=len(rows),boards=[v['file'] for v in boards])),flush=True)
    shutil.copy2(__file__,a.out/'executed_inspect.py')
    r.update(result='frames_decoded_not_yet_human_annotated',limits=[
        'Frame PTS is not independent A/V synchronization or ECU timing',
        'Coarse frames do not prove continuous unedited recording or pedal/load',
        'No audio inference, RPM identification, thermal-state claim or new timbre'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
