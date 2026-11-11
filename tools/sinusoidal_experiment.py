"""Offline AM/FM oscillator tracking experiment, never a sample runtime.
Tracks are fitted to the SAME excerpt; this is a reconstruction diagnostic,
not evidence that a general RPM/load engine model has been learned.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'python_deps'))
import numpy as np
import scipy.signal as sig
from scipy.optimize import linear_sum_assignment
import soundfile as sf
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def peaks(frame,sr,count):
    n=len(frame);win=np.hanning(n)
    z=np.fft.rfft(np.roll(frame*win,-n//2));magnitude=np.abs(z)
    indices=sig.find_peaks(20*np.log10(magnitude+1e-12),prominence=8,distance=3)[0]
    indices=indices[(indices>80*n/sr)&(indices<14000*n/sr)&(indices<len(z)-1)]
    indices=indices[np.argsort(magnitude[indices])[::-1]][:count]
    items=[]
    for k in indices:
        y=np.log(magnitude[k-1:k+2]+1e-20);den=y[0]-2*y[1]+y[2]
        delta=np.clip(.5*(y[0]-y[2])/den if abs(den)>1e-10 else 0,-.5,.5)
        response=np.sinc(delta)+.5*np.sinc(delta-1)+.5*np.sinc(delta+1)
        items.append([(k+delta)*sr/n,2*magnitude[k]/win.sum()/max(response,.1),np.angle(z[k])])
    return np.array(items).reshape(-1,3)

def add_interval(out,start,hop,sr,left,right):
    duration=hop/sr;t=np.arange(hop)/sr;ratio=t/duration
    fa,aa,pa=left;fb,ab,pb=right
    predicted=pa+np.pi*(fa+fb)*duration
    pb+=2*np.pi*round((predicted-pb)/(2*np.pi))
    delta=pb-pa;wa=2*np.pi*fa;wb=2*np.pi*fb
    c2=(3*delta-(2*wa+wb)*duration)/(duration*duration)
    c3=(-2*delta+(wa+wb)*duration)/(duration**3)
    phase=pa+wa*t+c2*t*t+c3*t*t*t
    out[start:start+hop]+=(aa+(ab-aa)*ratio)*np.cos(phase)

def synthesize(x,sr,count):
    size=4096;hop=256;out=np.zeros(len(x));previous=None;old_center=None
    for center in range(size//2,len(x)-size//2,hop):
        current=peaks(x[center-size//2:center+size//2],sr,count)
        if previous is not None:
            used_a=set();used_b=set()
            if len(previous) and len(current):
                cost=np.abs(previous[:,None,0]-current[None,:,0])/np.maximum(16,previous[:,None,0]*.045)
                rows,cols=linear_sum_assignment(cost)
                for i,j in zip(rows,cols):
                    if cost[i,j]>1:continue
                    add_interval(out,old_center,hop,sr,previous[i],current[j]);used_a.add(i);used_b.add(j)
            for i,a in enumerate(previous):
                if i not in used_a:add_interval(out,old_center,hop,sr,a,[a[0],0,a[2]+2*np.pi*a[0]*hop/sr])
            for j,b in enumerate(current):
                if j not in used_b:add_interval(out,old_center,hop,sr,[b[0],0,b[2]-2*np.pi*b[0]*hop/sr],b)
        previous=current;old_center=center
    return out

def main():
    folder=ROOT/'references/analysis/oscillator_experiment';folder.mkdir(exist_ok=True)
    test_sr=48000;test_t=np.arange(test_sr)/test_sr
    test=.25*np.cos(2*np.pi*223.7*test_t+.3)+.1*np.cos(2*np.pi*791.3*test_t-.4)
    reconstructed=synthesize(test,test_sr,16);valid=slice(9600,-9600)
    check_db=float(10*np.log10(np.mean((test[valid]-reconstructed[valid])**2)/np.mean(test[valid]**2)))
    assert check_db < -30,'Known off-bin sinusoidal control failed'
    x,sr=sf.read(ROOT/'references/clean/A_tailpipe_road_pull.wav',always_2d=True);x=x.mean(axis=1)
    outputs={'reference':x};report={}
    central=slice(sr//5,-sr//5)
    for count in (16,64):
        y=synthesize(x,sr,count);outputs[f'osc_{count}']=y
        report[str(count)]=dict(relative_waveform_residual_db=float(10*np.log10(np.mean((x[central]-y[central])**2)/np.mean(x[central]**2))),
            reconstructed_to_original_rms_db=float(10*np.log10(np.mean(y[central]**2)/np.mean(x[central]**2))))
    # For audition only, equalize RMS, then apply ONE shared peak-headroom gain.
    for key in outputs:outputs[key]*=10**(-23/20)/np.sqrt(np.mean(outputs[key][central]**2))
    scale=min(1,.85/max(np.max(np.abs(v)) for v in outputs.values()))
    for key,value in outputs.items():
        value=value*scale
        ramp=min(512,len(value)//4);value[:ramp]*=np.linspace(0,1,ramp);value[-ramp:]*=np.linspace(1,0,ramp)
        sf.write(folder/f'A_road_{key}_rms_matched.wav',value,sr,subtype='PCM_24')
    report.update(method='4096-sample Hann frames, 256-sample hop, tracked off-bin spectral peaks in 80 Hz..14 kHz, cubic phase interpolation, no noise model',
        known_two_tone_control_residual_db=check_db,
        limitations='Fitted to the same mono excerpt. Residual includes tracking/estimation/transient errors, analysis band limits and noise; it is NOT a noise-only measurement, method upper bound or perceptual score.',
        audition='Files matched by central-window unweighted RMS, not LUFS; then common peak headroom applied.')
    (folder/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    fig,ax=plt.subplots(figsize=(11,5),constrained_layout=True)
    for name,value in outputs.items():
        f,p=sig.welch(value,sr,nperseg=8192)
        ax.semilogx(f,10*np.log10(p+1e-20),label=name,alpha=.85)
    ax.set(xlim=(70,16000),ylim=(-135,-20),xlabel='Hz',ylabel='PSD (dB/Hz)',title='Same-excerpt oscillator reconstruction / RMS-matched for audition')
    ax.grid(alpha=.2);ax.legend();fig.savefig(folder/'spectral_comparison.png',dpi=150);plt.close(fig)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
