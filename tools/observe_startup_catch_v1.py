"""Observe the approved startup low-rise: no RPM labels or waveform modeling."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--ffmpeg', type=Path, required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from drive_evidence_v1.sources import read,sha
from drive_evidence_v1.family import peaks,follow

a.out.mkdir(parents=True,exist_ok=False)
(a.out/'frames').mkdir()
shutil.copy2(__file__,a.out/'executed_observer.py')
r=dict(result='running', physical_RPM_identified=False, source_sha256=sha(__file__),
       interpretation='Audio observations only; line families need independent phase qualification')
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    results={}
    fig,axes=plt.subplots(3,1,figsize=(13,10),constrained_layout=True)
    for index,ms in enumerate((80,160,320)):
        size=round(ms*.001*48000)
        hz,t,z=signal.stft(x,48000,nperseg=size,noverlap=size-240,axis=0,boundary=None,padded=False)
        power=np.mean(abs(z)**2,axis=1);t+=33
        axes[index].pcolormesh(t,hz,10*np.log10(np.maximum(power,1e-30)),vmin=-70,vmax=-12,shading='auto')
        axes[index].set(xlim=(37.1,39.8),ylim=(25,800),xlabel='Decoded source seconds',ylabel='Acoustic Hz',title=f'{ms} ms Hann; actual stereo total observation')
        rows=[]
        for time in np.arange(37.35,39.61,.25):
            i=int(np.argmin(abs(t-time)));freq,prom=peaks(hz,power[:,i])
            rows.append(dict(seconds=float(t[i]),peak_hz=freq.tolist(),prominence_dB=prom.tolist()))
        paths=[]
        for anchor in (7.,8.5,10.,12.,15.,17.5,20.,25.):
            for ref in (5,10,20):
                path=follow(hz,t,power,38.35,39.6,anchor,reference_multiple=ref,
                            check_multiples=(4,7,12),max_octaves_per_second=4,root_bounds=(5,30))
                if path['rows']:
                    values=np.array([v['root_hz'] for v in path['rows']])
                    support=np.array([v['independent_line_support'] for v in path['rows']])
                    paths.append(dict(anchor=anchor,reference=ref,root_range=[float(min(values)),float(max(values))],
                        independent2_support_fraction=float(np.mean(np.sum(support>0,axis=1)>=2)),rows=path['rows']))
        results[str(ms)]=dict(peaks=rows,paths=paths)
    fig.savefig(a.out/'low_rise_spectrogram.png',dpi=130);plt.close(fig)
    r['windows']=results
    # Source frames stay at native resolution, with exact PTS in decode logs.
    cat=json.loads((a.workspace/'references/segments_v1.json').read_text(encoding='utf-8'))
    source=cat['sources']['A'];video=a.workspace/source['video'];assert sha(video)==source['video_sha256']
    cmd=[str(a.ffmpeg),'-v','info','-nostdin','-n','-to','40.1','-i',str(video),'-vf',
         "select='between(t,36.9,40)*not(mod(n,15))',showinfo",'-fps_mode','vfr',str(a.out/'frames/frame_%03d.png')]
    done=subprocess.run(cmd,capture_output=True,timeout=60)
    (a.out/'frames/decode.log').write_bytes(done.stderr);assert done.returncode==0
    frames=list(sorted((a.out/'frames').glob('frame_*.png')));assert frames
    board=Image.new('RGB',(1280,390*((len(frames)+1)//2)),'#101820')
    draw=ImageDraw.Draw(board);font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',18)
    for i,path in enumerate(frames):
        with Image.open(path) as im:
            im=im.resize((640,360));board.paste(im,(i%2*640,i//2*390))
        draw.text((i%2*640+8,i//2*390+362),path.name,font=font,fill='white')
    board.save(a.out/'frames/contact.png')
    r.update(result='observed',video_sha256=sha(video),video_command=cmd,
             source_frames={v.name:sha(v) for v in frames},max_abs_LR=np.max(abs(x),axis=0).tolist())
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],paths={k:[{f:v[f] for f in ('anchor','reference','root_range','independent2_support_fraction')} for v in rows['paths']] for k,rows in r['windows'].items()})))
