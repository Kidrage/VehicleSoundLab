"""Local PCM WAV diagnostics and steady-state oscillator DNA extraction.

No network access. RPM and note/root frequency are supplied, never guessed as fact.
Requires NumPy. Measurements describe the selected window, not an entire vehicle.
"""
import argparse
import hashlib
import json
import wave
from pathlib import Path
import numpy as np

def read_pcm(path,start=0,duration=30):
    with wave.open(str(path),'rb') as f:
        sr=f.getframerate(); channels=f.getnchannels(); width=f.getsampwidth(); total=f.getnframes()
        if channels not in (1,2):raise ValueError('Use mono or stereo PCM WAV')
        first=min(total,int(start*sr)); f.setpos(first)
        data=f.readframes(min(total-first,int(duration*sr)))
    if width==2: x=np.frombuffer(data,'<i2').astype(np.float64)/32768
    elif width==3:
        b=np.frombuffer(data,np.uint8).reshape(-1,3).astype(np.int32)
        v=b[:,0]|(b[:,1]<<8)|(b[:,2]<<16); v=np.where(v&0x800000,v-0x1000000,v)
        x=v/8388608.0
    elif width==4:x=np.frombuffer(data,'<i4').astype(np.float64)/2147483648
    else:raise ValueError('Decode to PCM 16/24/32 WAV first')
    if not len(x):raise ValueError('Selected window is empty')
    return x.reshape(-1,channels),sr,total/sr

def measure(x,sr,rpm=None,cylinders=10):
    mono=x.mean(axis=1); size=8192; hop=1024
    if len(mono)<size: mono=np.pad(mono,(0,size-len(mono)))
    windows=np.lib.stride_tricks.sliding_window_view(mono,size)[::hop]
    win=np.hanning(size); power=np.zeros(size//2+1)
    # Bounded batch allocation, including long source files.
    for first in range(0,len(windows),128):
        power+=(np.abs(np.fft.rfft(windows[first:first+128]*win,axis=1))**2).sum(axis=0)
    power/=max(1,len(windows)); freq=np.fft.rfftfreq(size,1/sr)
    total=max(float(power.sum()),1e-30)
    rms=float(np.sqrt(np.mean(x*x))); peak=float(np.max(np.abs(x)))
    result=dict(sample_rate=sr,analyzed_seconds=len(x)/sr,channels=x.shape[1],
        peak_dbfs=float(20*np.log10(max(peak,1e-15))),rms_dbfs=float(20*np.log10(max(rms,1e-15))),
        crest_db=float(20*np.log10(max(peak,1e-15)/max(rms,1e-15))),
        clipped_sample_fraction=float(np.mean(np.abs(x)>=.999)),
        channel_dc=x.mean(axis=0).tolist(),
        centroid_hz=float(np.sum(freq*power)/total),
        rolloff_95_hz=float(freq[min(len(freq)-1,int(np.searchsorted(np.cumsum(power),.95*total)))]),
        spectral_flatness=float(np.exp(np.mean(np.log(power[1:]+1e-30)))/max(float(power[1:].mean()),1e-30)),
        bands_db={f'{lo}_{hi}':float(10*np.log10(max(float(power[(freq>=lo)&(freq<hi)].sum())/total,1e-30)))
            for lo,hi in ((28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,20000))})
    if rpm:
        firing=cylinders*rpm/120
        distance=np.abs(freq/firing-np.rint(freq/firing))*firing
        mask=(distance<1.5*sr/size)&(freq>firing*.5)
        result.update(manual_rpm=rpm,cylinders=cylinders,firing_hz=firing,
            firing_harmonic_energy_fraction=float(power[mask].sum()/total),
            rpm_warning='Manual RPM applies only if this selected window is steady; no CAN/tachometer validation.')
    return result

def export_dna(x,sr,root,path):
    mono=x.mean(axis=1); n=min(128,int(sr*.44/root))
    if root<10 or root>4000 or n<1:raise ValueError('Root must be 10..4000 Hz')
    t=np.arange(len(mono))/sr; win=np.hanning(len(mono)); weighted=mono*win
    amps=[]; phases=[]; approximation=np.zeros_like(mono)
    for k in range(1,n+1):
        z=2*np.sum(weighted*np.exp(-2j*np.pi*root*k*t))/max(win.sum(),1)
        amps.append(float(abs(z))); phases.append(float(np.angle(z)))
        approximation+=np.real(z*np.exp(2j*np.pi*root*k*t))
    path.write_text(f'VSL_DNA 1 {root:.12g} {n}\n'+''.join(f'{a:.12g} {p:.12g}\n' for a,p in zip(amps,phases)),encoding='utf-8')
    residual=float(np.sqrt(np.mean((mono-approximation)**2)))
    signal=float(np.sqrt(np.mean(mono**2)))
    return dict(file=str(path),root_hz=root,partials=n,fit_residual_to_signal_db=float(20*np.log10(max(residual,1e-15)/max(signal,1e-15))),
        scope='Single steady harmonic snapshot; envelopes, unison/chorus, FM and noise require additional model dimensions.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('wav',type=Path); p.add_argument('--start',type=float,default=0)
    p.add_argument('--duration',type=float,default=30); p.add_argument('--rpm',type=float)
    p.add_argument('--cylinders',type=int,default=10); p.add_argument('--json',type=Path)
    p.add_argument('--export-dna',type=Path); p.add_argument('--root-hz',type=float)
    a=p.parse_args()
    if a.start<0 or not 0<a.duration<=240:p.error('start >= 0; duration 0..240 seconds per window')
    if a.rpm is not None and not 0<a.rpm<=20000:p.error('RPM must be positive')
    x,sr,total=read_pcm(a.wav,a.start,a.duration)
    report=measure(x,sr,a.rpm,a.cylinders)
    report.update(file=str(a.wav.resolve()),file_sha256=hashlib.sha256(a.wav.read_bytes()).hexdigest(),
        source_total_seconds=total,window_start_seconds=a.start)
    if a.export_dna:
        if a.root_hz is None:p.error('--export-dna requires an explicitly known --root-hz')
        report['dna']=export_dna(x,sr,a.root_hz,a.export_dna)
    output=a.json or a.wav.with_suffix('.analysis.json')
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
