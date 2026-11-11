"""Recording comb observations and primary-source ledger for V0.6 geometry.

No recording is treated as separated bank pressure or known RPM telemetry.
"""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'references/analysis/bank_geometry_v1'
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw,ImageFont
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def comb_observation(x,sr):
    hz,p=signal.welch(x,sr,nperseg=8192,noverlap=4096,axis=0,detrend=False)
    p=p.mean(axis=1)  # Channel powers, never a binaural waveform collapse.
    db=10*np.log10(p+1e-30)
    peaks,props=signal.find_peaks(db,prominence=9,distance=3)
    peaks=peaks[(hz[peaks]>80)&(hz[peaks]<1500)&(db[peaks]>db.max()-32)]
    refined=[]
    for k in peaks:
        q=np.log(p[k-1:k+2]+1e-30)
        shift=.5*(q[0]-q[2])/(q[0]-2*q[1]+q[2])
        refined.append((k+np.clip(shift,-.5,.5))*sr/8192)
    refined=np.array(refined);weights=np.sqrt(p[peaks]);weights/=max(weights.sum(),1e-30)
    scores=[]
    for spacing in np.arange(30,180.01,.25):
        distance=abs(refined/spacing-np.rint(refined/spacing))*spacing
        # Coarse spectral-comb diagnostic; subharmonics and recording transfer
        # can create multiple plausible solutions. Retain alternatives.
        score=float(np.sum(weights*np.exp(-.5*(distance/5)**2)))
        scores.append(score)
    choices=signal.find_peaks(scores,distance=12)[0]
    choices=choices[np.argsort(np.array(scores)[choices])[::-1]][:6]
    return hz,p,dict(window_frames=8192,frequency_bin_hz=sr/8192,
        prominent_peak_hz=refined.tolist(),peak_weights=weights.tolist(),
        spacing_candidates=[dict(hz=float(30+.25*i),score=float(scores[i])) for i in choices],
        limits='Coarse harmonic-comb observation, not RPM, bank phase, load or an identified engine impulse train.')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cases=[('A_idle','A',208,211),('A_revs_early','A',238,242),
           ('A_revs_late','A',244,248),('A_moving','A',316,319.5),('B_cabin','B',218,222)]
    result=dict(schema='vsl.bank-geometry-observations/1',runtime_change='0.6.0',recordings={},sources={})
    fig,axes=plt.subplots(3,1,figsize=(11,10),layout='constrained')
    angles_old=np.arange(10)*72
    angles_new=np.array([0,90,144,234,288,378,432,522,576,666])
    for y,angles,name in [(1,angles_old,'V0.5: even 72 crank degrees'),(0,angles_new,'V0.6: common-pin 90 / 54 crank degrees')]:
        for index,angle in enumerate(angles):
            axes[0].vlines(angle,y,y+.6,color='C0' if index%2==0 else 'C1',lw=3)
        axes[0].text(715,y+.72,name,ha='right',fontsize=10)
    axes[0].set_xlim(-10,730);axes[0].set_ylim(-.1,2.1);axes[0].set_xlabel('Crank degrees across a 720-degree cycle');axes[0].set_yticks([])
    n=np.arange(1,17)
    for offset,name in [(72,'Even pair'),(90,'Common-pin pair')]:
        amplitude=2*abs(np.cos(np.pi*n*offset/144))
        axes[1].plot(n,amplitude,'o-',label=name)
    axes[1].set_xlabel('Bank harmonic number');axes[1].set_ylabel('Ideal summed pair amplitude')
    axes[1].set_title('Ideal geometry only: no manifold delay, unequal gains or room');axes[1].legend();axes[1].grid(alpha=.2)
    for name,source,start,end in cases:
        file=ROOT/f'references/clean/{source}_decoded_float.wav'
        with sf.SoundFile(file) as f:
            assert f.samplerate==48000 and f.subtype=='FLOAT' and f.channels==2
            f.seek(round(start*48000));x=f.read(round((end-start)*48000),always_2d=True)
        hz,p,item=comb_observation(x,48000);item['source']=source;item['source_seconds']=[start,end]
        item['use']='Candidate spacing only in this low-rev recording span; alternatives retained.' if name in ['A_idle','A_revs_late'] else 'Nonstationary or mixed-source aggregate: do not use these candidates as engine pitch.'
        result['recordings'][name]=item
        result['sources'][source]=dict(master=str(file.relative_to(ROOT)).replace('\\','/'),sha256=sha(file))
        if name in ['A_idle','A_revs_late']:
            mask=(hz>=28)&(hz<=1500)
            axes[2].plot(hz[mask],10*np.log10(p[mask]/p.max()+1e-30),label=f'{name}: recording, unknown RPM')
        with (OUT/f'{name}_spectrum.csv').open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['frequency_hz','channel_mean_psd']);w.writerows(zip(hz,p))
    axes[2].set_xlabel('Hz');axes[2].set_ylabel('dB relative to recording peak');axes[2].set_xlim(28,1500);axes[2].set_ylim(-65,2);axes[2].legend();axes[2].grid(alpha=.2)
    fig.suptitle('Combustion geometry and recording observations are separate evidence')
    fig.savefig(OUT/'geometry_and_recordings.png',dpi=150);plt.close(fig)
    times=[239,241,243,245,247]
    board=Image.new('RGB',(1000,660),(20,25,34));draw=ImageDraw.Draw(board)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    for i,seconds in enumerate(times):
        file=OUT/f'A_frame_{seconds}.jpg'
        subprocess.run(['D:/repo/tools/ffmpeg/bin/ffmpeg.exe','-v','error','-nostdin','-y','-ss',str(seconds),
            '-i',str(ROOT/'references/raw/A_context_360p.mp4'),'-frames:v','1',str(file)],check=True)
        with Image.open(file) as im:
            im.thumbnail((500,285));x=(i%2)*500;y=(i//2)*220
            im.thumbnail((490,190));board.paste(im,(x,y))
            draw.text((x+8,y+193),f'A source {seconds} s',font=font,fill='white')
    board.save(OUT/'stationary_video_context.jpg')
    result['video_context']=dict(video='references/raw/A_context_360p.mp4',sha256=sha(ROOT/'references/raw/A_context_360p.mp4'),
        sampled_source_seconds=times,contact_sheet='stationary_video_context.jpg',
        scope='Sampled stationary rear context; frames do not establish pedal, gear, exact RPM or absence of all edits.')
    tech=ROOT/'research/technical_sources'
    primary=[]
    for name in ['audi_52_engine','audi_2019_engine']:
        meta=json.loads((tech/f'{name}.provenance.json').read_text())
        assert sha(tech/f'{name}.html')==meta['sha256']
        text=(tech/f'{name}.txt').read_text(encoding='utf-8')
        # Save the exact paragraph; do not mistake a search snippet for the source.
        at=text.find('common crankpin')
        if at<0:at=text.find('shared crank pin')
        assert at>=0
        excerpt=text[max(0,at-220):at+420]
        assert '54' in excerpt and '90' in excerpt
        primary.append(dict(**meta,local_html=str((tech/f'{name}.html').relative_to(ROOT)).replace('\\','/'),exact_excerpt=excerpt))
    ledger=dict(primary=primary,
        target_link=dict(source='https://en.wikipedia.org/wiki/Lamborghini_V10',
            local_html='research/technical_sources/lamborghini_v10_wiki.html',sha256=sha(tech/'lamborghini_v10_wiki.html'),
            scope='Secondary description distinguishes 5.0 split-pin 72 degrees from 5.2 shared-pin 90/54; R8/Huracan family relationship is indirect evidence, not an inspected Performante crank drawing.'),
        rejected_number=dict(source='https://www.evo.co.uk/lamborghini/gallardo/8876/lamborghini-gallardo-lp560-4-new-gallardo-v10-bends-design-rules',
            local_html='research/technical_sources/evo_52.html',sha256=sha(tech/'evo_52.html'),
            observation='Article prints 90/58. Five pairs would total 740 degrees, inconsistent with a 720-degree four-stroke cycle. Do not use 58; official Audi explicitly specifies 54.'),
        unavailable_training_pdf='VAG Links 990193 URLs returned 404, archive 429. No PDF content was inspected or used.',
        modelling_conventions=['Bank L starts at 0 and bank R at 90 crank degrees. Source establishes alternating gaps, not a measured bank-to-microphone orientation.',
            'Bank delay .00038 s, individual cylinder weights and the spectral envelope remain unmeasured engineering settings.',
            'Audio recordings do not independently identify bank phase, exact RPM, firing order or manifold branches.',
            'V6 has equal half-bank phasor spacing for its Ferrari-context V10. Retain its module/control methodology while specializing geometry for the 5.2 family.'])
    (OUT/'technical_evidence.json').write_text(json.dumps(ledger,indent=2,ensure_ascii=False),encoding='utf-8')
    result['technical_evidence']='technical_evidence.json'
    result['script_sha256']=sha(Path(__file__))
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v['spacing_candidates'][:3] for k,v in result['recordings'].items()},indent=2))

if __name__=='__main__':main()
