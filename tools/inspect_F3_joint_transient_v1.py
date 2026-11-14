"""Four new native-PTS frames near the retained HF peak, no audio processing."""
import argparse
from fractions import Fraction
from pathlib import Path
import re
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image,ImageDraw
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',frames=[],source_hashes={})
try:
    for name in ['tools/inspect_F3_joint_transient_v1.py','research/F3_driver_joint_v1_transient_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['source_hashes'][name]=sha(dest)
    plan=load(repo/'research/F3_driver_joint_v1_transient_plan.json')
    cat=load(a.workspace/'references/segments_v1.json');s=cat['sources']['F3'];video=a.workspace/s['video']
    assert sha(video)==s['video_sha256']
    windows=plan['time_windows_seconds'];select='+'.join(f'between(t,{lo},{hi})' for lo,hi in windows)
    command=[r'D:\repo\tools\ffmpeg\bin\ffmpeg.exe','-hide_banner','-nostdin','-n','-threads','2','-ss','190.5','-copyts','-i',str(video),'-an','-vf',f"select='{select}',showinfo",'-frames:v','4','-fps_mode','vfr','-q:v','2',str(a.out/'frame_%02d.jpg')]
    done=subprocess.run(command,capture_output=True,timeout=180);(a.out/'decode.log').write_bytes(done.stderr);assert done.returncode==0
    matches=re.findall(r'\bn:\s*(\d+) pts:\s*(-?\d+) pts_time:([-\d.]+)',done.stderr.decode('utf8',errors='replace'))
    assert len(matches)==4,matches
    board=Image.new('RGB',(1920,1152),'#161b22');draw=ImageDraw.Draw(board)
    for i,(number,pts,shown) in enumerate(matches):
        seconds=float(int(pts)*Fraction(1,1000));assert windows[i][0]<=seconds<=windows[i][1]
        assert abs(seconds-float(shown))<.001
        path=a.out/f'frame_{int(number)+1:02d}.jpg'
        with Image.open(path) as picture:board.paste(picture.resize((960,540)),((i%2)*960,(i//2)*576))
        draw.text(((i%2)*960+8,(i//2)*576+546),f'{seconds:.3f}s | original PTS {pts}',fill='white')
        r['frames'].append(dict(file=path.name,pts=int(pts),source_seconds=seconds,sha256=sha(path)))
    board.save(a.out/'context.png')
    r.update(result='four_new_original_PTS_frames_prepared',video=str(video),video_sha256=sha(video),command=command,time_base='1/1000',context_sha256=sha(a.out/'context.png'),manual_reviewed=False,physical_event_identified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['result'])
