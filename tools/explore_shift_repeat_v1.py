"""Inspect the approved first Corsa passage as an independent shift candidate."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy import signal
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe
from drive_evidence_v1.family import follow,peaks
args.out.mkdir(parents=True,exist_ok=False)
audio,provenance=read(args.workspace,'E_corsa_first_context','cabin_dynamic_observation')
other,other_provenance=read(args.workspace,'E_corsa_second_context','cabin_dynamic_observation')
observed=observe(audio,47,80)
families=[]
for start in (47.5,48.,48.5,49.):
    for anchor in (35,45,55,65):
        family=follow(observed['hz'],observed['seconds'],observed['power_low'],start,54.8,anchor,
                      max_octaves_per_second=32)
        families.append(dict(start=start,anchor_root=anchor,**family))
np.savez_compressed(args.out/'spectrum.npz',seconds=observed['seconds'],hz=observed['hz'],power=observed['power_low'])

# Common-gain-invariant sample correlation, not proof of independence. This does
# not test duplication after changes in pitch, phase, codec or spectral envelope.
# Delay search is performed on lowpassed 4kHz L/R for the full8s passage.
rate=4000
a=signal.resample_poly(audio,1,12,axis=0);b=signal.resample_poly(other,1,12,axis=0)
correlations=[]
for channel in range(2):
    x=a[:,channel]-a[:,channel].mean();y=b[:,channel]
    dot=signal.correlate(y,x,mode='valid',method='fft')
    energy=signal.convolve(y*y,np.ones(len(x)),mode='valid',method='fft')
    mean=signal.convolve(y,np.ones(len(x)),mode='valid',method='fft')/len(x)
    norm=np.sqrt(np.maximum(energy-len(x)*mean*mean,1e-30)*np.sum(x*x))
    score=dot/norm;at=int(np.argmax(abs(score)))
    correlations.append(dict(channel=channel,maximum_absolute_correlation=float(abs(score[at])),
        second_passage_seconds=float(82+at/rate),rate=rate))

catalog=json.loads((args.workspace/'references/segments_v1.json').read_text(encoding='utf-8'))
source=catalog['sources']['E'];video=args.workspace/source['video'];assert sha(video)==source['video_sha256']
index_path=args.workspace/'references/analysis/DE_usability_v1/E/video_frames.json'
index=json.loads(index_path.read_text(encoding='utf-8'));base=Fraction(index['time_base'])
by_pts={int(frame['best_effort_timestamp']):i for i,frame in enumerate(index['all_frames'])}
command=['D:/repo/tools/ffmpeg/bin/ffmpeg.exe','-v','info','-nostdin','-n','-to','55.1','-i',str(video),
         '-vf',"select='between(t,47,55)*not(mod(n,15))',crop=1280:600:100:180,showinfo",'-fps_mode','vfr',str(args.out/'frame_%03d.png')]
run=subprocess.run(command,capture_output=True,check=True);(args.out/'decode.log').write_bytes(run.stderr)
parsed=re.findall(r'\bn:\s*(\d+) pts:\s*(\d+) pts_time:([\d.]+)',run.stderr.decode('utf-8',errors='replace'))
frames=[]
for number,pts,shown in parsed:
    pts=int(pts);seconds=float(pts*base);assert abs(seconds-float(shown))<.001
    path=args.out/f'frame_{int(number)+1:03d}.png'
    frames.append(dict(file=path.name,sha256=sha(path),pts=pts,source_frame=by_pts[pts],seconds=seconds))
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',17)
for first in range(0,len(frames),8):
    subset=frames[first:first+8];board=Image.new('RGB',(1280,330*((len(subset)+1)//2)),'#101922');draw=ImageDraw.Draw(board)
    for i,row in enumerate(subset):
        x,y=(i%2)*640,(i//2)*330
        with Image.open(args.out/row['file']) as im:board.paste(im.resize((640,300)),(x,y))
        draw.text((x+8,y+303),f"{row['seconds']:.3f}s | frame {row['source_frame']}",font=font,fill='white')
    board.save(args.out/f'sheet_{first//8+1:02d}.jpg',quality=95)
report=dict(schema='vsl.shift-repeat-exploration/1',provenance=provenance,comparison_provenance=other_provenance,
            video_sha256=sha(video),video_time_base=index['time_base'],index_sha256=sha(index_path),video_command=command,
            frames=frames,duplicate_audio_diagnostic=correlations,families=families,
            source_sha256={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))},
            limits=['No measured pedal/load or independent AV/cluster latency',
                    'Low waveform correlation alone does not prove separate driving runs',
                    'Candidate families are alternatives, not independent repeated evidence'])
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(connected=[dict(start=f['start'],anchor=f['anchor_root']) for f in families if f['rows']],
                      frames=len(frames),correlations=correlations),ensure_ascii=False))
