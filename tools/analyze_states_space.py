"""Measure approved stereo clips without modifying them; annotate only visible evidence."""
from pathlib import Path
import sys,json,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from PIL import Image,ImageDraw,ImageFont
out=ROOT/'references/analysis/v02';out.mkdir(exist_ok=True)
rows=[]
for catalog in ['A_clip_catalog.json','B_clip_catalog.json','v02/context_catalog.json']:
    for clip in json.loads((ROOT/'references/analysis'/catalog).read_text(encoding='utf-8')):
        x,sr=sf.read(clip['file'],always_2d=True)
        row=dict(name=clip['name'],source_start=clip['start'],duration=len(x)/sr,bands=[])
        row['camera_cut_warning']=clip['name'] in ['A_corsa_tailpipe_idle','A_tailpipe_road_pull']
        f,pl=signal.welch(x[:,0],sr,nperseg=4096)
        _,pr=signal.welch(x[:,1],sr,nperseg=4096)
        _,cross=signal.csd(x[:,0],x[:,1],sr,nperseg=4096)
        _,coh=signal.coherence(x[:,0],x[:,1],sr,nperseg=4096)
        for lo,hi in [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,16000)]:
            mask=(f>=lo)&(f<hi);power=(pl+pr)[mask].sum()
            mid=(pl+pr+2*cross.real)[mask].sum()/4
            side=(pl+pr-2*cross.real)[mask].sum()/4
            row['bands'].append(dict(lo=lo,hi=hi,energy_fraction=float(power/(pl+pr).sum()),
                side_to_mid_db=float(10*np.log10(max(side,1e-30)/max(mid,1e-30))),
                lr_level_db=float(10*np.log10(max(pl[mask].sum(),1e-30)/max(pr[mask].sum(),1e-30))),
                mean_magnitude_squared_coherence=float(np.average(coh[mask],weights=(pl+pr)[mask]+1e-30))))
        # Time-resolved band envelopes reveal attacks and releases, not absolute torque/RPM.
        t,env=[],[]
        for start in range(0,len(x)-4800,2400):
            s=x[start:start+4800];p=np.abs(np.fft.rfft(s*np.hanning(len(s))[:,None],axis=0))**2
            freq=np.fft.rfftfreq(len(s),1/sr)
            t.append(clip['start']+start/sr)
            env.append([float(10*np.log10(max(p[(freq>=lo)&(freq<hi)].sum(),1e-30))) for lo,hi in [(28,400),(400,3000),(3000,16000)]])
        row['envelope_times_source_seconds']=t;row['relative_band_envelopes_db']=env
        rows.append(row)
result=dict(scope='Approved A/B; Welch stereo band statistics. Coherence is not source separation or room identification.',
    observations='A camera position known; microphone unknown. B is local MP3 without video; no visual driving-state claim.',clips=rows)
(out/'stereo_state_metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
times=[31,33,35,37,39,208,213,238,243,248,313.5,315,316.5,318,319.5]
board=Image.new('RGB',(1200,5*250),(20,25,34));draw=ImageDraw.Draw(board)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
for i,t in enumerate(times):
    frame=out/f'A_{str(t).replace(".","_")}.jpg'
    subprocess.run(['D:/repo/tools/ffmpeg/bin/ffmpeg.exe','-v','error','-nostdin','-y','-ss',str(t),'-i',str(ROOT/'references/raw/A_context_360p.mp4'),'-frames:v','1',str(frame)],check=True)
    im=Image.open(frame);im.thumbnail((400,225));xx=i%3*400;yy=i//3*250
    board.paste(im,(xx,yy));draw.text((xx+8,yy+226),f'A source {t:g} s',font=font,fill='white')
board.save(out/'A_state_context.jpg')
for r in rows:
    print(r['name'], ' | '.join(f"{b['lo']}-{b['hi']}: S/M {b['side_to_mid_db']:.1f}dB, coh {b['mean_magnitude_squared_coherence']:.2f}" for b in r['bands'][::2]))
