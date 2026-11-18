"""Bounded, reproducible acoustic/visual-reference evidence; no runtime fitting claim."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal

def main():
    p=argparse.ArgumentParser();p.add_argument('--audio',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    x,rate=sf.read(a.audio,dtype='float32',always_2d=True)
    assert rate==48000
    windows=[('User-link-context',32.,43.),('Intro-crackle-context',3.3,6.3),
        ('Flame-pass-1',152.8,153.7),('Flame-pass-2',155.3,156.4),('Flame-pass-3',156.8,157.9),
        ('Night-flame-1',444.,446.5),('Night-flame-2',446.6,449.8)]
    rows=[]
    for name,lo,hi in windows:
        crop=x[round(lo*rate):round(hi*rate)];y=crop.mean(axis=1)
        sf.write(a.output/(name+'.wav'),crop,rate,subtype='FLOAT')
        f,t,z=signal.stft(y,rate,nperseg=512,noverlap=392,boundary=None)
        psd=abs(z)**2
        band_power={f'{l}-{h}':np.mean(np.sum(psd[(f>=l)&(f<h)],axis=0)).item()
            for l,h in [(60,500),(500,2500),(2500,6000),(6000,12000)]}
        mid=np.sqrt(np.sum(psd[(f>=500)&(f<2500)],axis=0))
        high=np.sqrt(np.sum(psd[(f>=2500)&(f<12000)],axis=0))
        flux=np.maximum(np.diff(np.log(1e-6+mid)),0)+np.maximum(np.diff(np.log(1e-6+high)),0)
        peaks,_=signal.find_peaks(flux,height=.9,prominence=.65,distance=12)
        times=t[peaks+1]+lo
        intervals=np.diff(times)
        intervals=intervals[(intervals>=.03)&(intervals<=.30)]
        rows.append(dict(name=name,first_frame=round(lo*rate),last_frame=round(hi*rate),
            rms=float(np.sqrt(np.mean(crop.astype(float)**2))),peak=float(np.max(abs(crop))),
            band_power=band_power,acoustic_onset_candidates_seconds=times.tolist(),
            candidate_interval_percentiles_ms=(np.percentile(intervals,[10,50,90])*1000).tolist() if len(intervals) else [],
            physically_isolated=False))
    report=dict(schema='vsl.afterfire-reference-G/1',source_id='G',url='https://www.youtube.com/watch?v=7BMsB7jUxqc',
        audio_sha256=hashlib.sha256(a.audio.read_bytes()).hexdigest(),decoded_frames=len(x),sample_rate=rate,
        decoded_seconds=len(x)/rate,contexts=rows,normalisation=False,
        visual_review='Exact-frame full-video 5 s screening; 151-159 s and 444-452 s inspected every 0.2 s. Visible flames approx 153.2,155.6-156.0,157.0-157.6,444.0,444.4,446.8-449.6 s. Flame visibility does not timestamp every audible crack. Earlier fps-nearest thumbnails had a 2.5 s label offset; use frames_exact and storyboard-exact files.',
        interpretation='Intro acoustical intervals guide a bounded irregular burst; mid/high broad transient energy guides short noise-band excitation. Three chosen damped modal frequencies and decay constants remain engineering parameters, not identified pipe/body modes.',
        cautions=['Modified V12 reference, separate from the V10 DNA','Mixed sources and propagation remain; flame does not prove a pedal release',
            'No ECU/RPM/pedal measurements, A/V offset calibration or isolated pop ground truth',
            'The full-file decoder reported an Opus packet-header warning; 620.553 s decoded. Crops avoid the file end; compressed-audio overshoots are not evidence of microphone clipping.'])
    (a.output/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(contexts=len(rows),intro_interval_ms=rows[1]['candidate_interval_percentiles_ms']),ensure_ascii=False))

if __name__=='__main__':main()
