"""Three coarse spectra and bounded shared acoustic AM, not a PCM timeline.

Only approved A exterior 47.60..48.18s is used. Spectral peak widths include
analysis broadening; generated widths/coherence remain engineering controls.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy import signal
import soundfile as sf
from startup_character_v1.author import write_profile
from startup_character_v1.expression import smooth_curve
RATE=48000
BANDS=[(80,300),(300,650),(650,790),(790,960),(960,1250),(1250,2200),(2200,4000),(4000,8000)]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def shared_am(x):
    n=len(x);t=np.arange(n)/RATE;rows=[]
    for low,high in BANDS:
        y=signal.sosfiltfilt(signal.butter(3,[low,high],fs=RATE,btype='bandpass',output='sos'),x.mean(axis=1))
        e=abs(signal.hilbert(y));e=signal.sosfiltfilt(signal.butter(2,55,fs=RATE,output='sos'),e)
        trend=signal.sosfiltfilt(signal.butter(2,4,fs=RATE,output='sos'),e)
        rows.append(e/np.maximum(trend,np.mean(e)*.3)-1)
    rows=np.array(rows);valid=(t>.045)&(t<t[-1]-.045)
    scores=[]
    for hz in np.arange(6,22.01,.1):
        a=np.array([np.cos(2*np.pi*hz*t),np.sin(2*np.pi*hz*t),np.cos(4*np.pi*hz*t),np.sin(4*np.pi*hz*t)]).T
        beta=np.linalg.lstsq(a[valid],rows[:,valid].T,rcond=None)[0].T
        explained=1-np.mean((rows[:,valid]-beta@a[valid].T)**2,axis=1)/np.maximum(np.mean(rows[:,valid]**2,axis=1),1e-15)
        # Robust score across bands; no one-band clock/physical identity claim.
        scores.append((float(np.median(explained)),float(hz),beta,explained))
    score,hz,beta,explained=max(scores,key=lambda r:r[0])
    beta*=np.minimum(1,.40/np.maximum(abs(beta).sum(axis=1),1e-15))[:,None]
    return hz,beta[:,[0,2]],beta[:,[1,3]],dict(score=score,band_explained=explained.tolist(),limits='Single short mixed acoustic action, not independent rotation/load identification. Bounded AM is a design allocation; beating/noise also contribute to observed envelopes.')

def fir_from_psd(psd):
    mag=np.sqrt(np.maximum(psd,np.max(psd)*1e-9));cep=np.fft.irfft(np.log(mag),n=16384)
    causal=np.zeros_like(cep);causal[0]=cep[0];causal[1:8192]=2*cep[1:8192];causal[8192]=cep[8192]
    h=np.fft.irfft(np.exp(np.fft.rfft(causal)),n=16384)[:8192];h[-512:]*=np.linspace(1,0,512)
    desired=np.trapezoid(psd,dx=RATE/16384)
    h*=np.sqrt(desired)/max(1e-15,np.linalg.norm(h));return h

def build(source,output,old_profile):
    output.mkdir(parents=True,exist_ok=False)
    with sf.SoundFile(source) as f:f.seek(round(47.60*RATE));x=f.read(round(.58*RATE),dtype='float64');assert f.samplerate==RATE and f.channels==2
    old=json.loads(old_profile.read_text());env=np.array(old['envelope']);contour=smooth_curve(np.arange(len(x))/len(x),np.linspace(0,1,9),env);y=x/contour[:,None]
    f,psd=signal.welch(y,fs=RATE,axis=0,nperseg=4096,noverlap=2048,nfft=16384)
    mean=psd.mean(axis=1);peaks,_=signal.find_peaks(mean,distance=3)
    low=[k for k in peaks if 80<=f[k]<4000];high=[k for k in peaks if 4000<=f[k]<=8000]
    selected=sorted(sorted(low,key=lambda k:mean[k],reverse=True)[:80]+sorted(high,key=lambda k:mean[k],reverse=True)[:16])
    widths=signal.peak_widths(mean,selected,rel_height=.5)[0]*RATE/16384
    hz,cosine,sine,am_report=shared_am(y)
    modes=[];ownership=np.zeros(len(f));state_psd=[]
    for part in np.array_split(y,3):state_psd.append(signal.welch(part,fs=RATE,axis=0,nperseg=4096,noverlap=2048,nfft=16384)[1])
    # Fixed L/R phase relation at each carrier; no framewise stored phase path.
    window=signal.windows.hann(4096,sym=False);t=np.arange(4096)/RATE
    for j,k in enumerate(selected):
        left=max(80,(f[selected[j-1]]+f[k])/2) if j else 80
        right=min(8000,(f[selected[j+1]]+f[k])/2) if j+1<len(selected) else 8000
        keep=(f>=max(left,f[k]-38))&(f<min(right,f[k]+38))
        # Leave broad residual detail. Narrow OSC energy is not a physically
        # isolated mechanical share; partition is explicitly editable.
        ownership[keep]=.72
        amplitude=[np.sqrt(2*np.sum(p[keep],axis=0)*(RATE/16384)*.72).tolist() for p in state_psd]
        z=np.sum(y[:4096]*window[:,None]*np.exp(-2j*np.pi*f[k]*t)[:,None],axis=0)
        modes.append(dict(hz=float(f[k]),width_hz=float(np.clip(widths[j]*.55,3,45)),amplitude=amplitude,phase=np.angle(z).tolist(),band=next(i for i,(lo,hi) in enumerate(BANDS) if lo<=f[k]<hi or i==7)))
    profiles=[]
    for i,part in enumerate(np.array_split(y,3)):
        ms=np.stack(((part[:,0]+part[:,1])/np.sqrt(2),(part[:,0]-part[:,1])/np.sqrt(2)),axis=1)
        spectra=signal.welch(ms,fs=RATE,axis=0,nperseg=4096,noverlap=2048,nfft=16384)[1]
        path=output/f'rotation-residual-{i}.sfir';write_profile(path,[fir_from_psd(spectra[:,c]*(1-ownership)) for c in range(2)])
        profiles.append(dict(path=str(path.resolve()),sha256=sha(path)))
    rotation=dict(schema='vsl.crank-rotation/1',modes=modes,bands=BANDS,flutter_hz=hz,cosine=cosine.tolist(),sine=sine.tolist(),coherence=.35)
    doc=dict(schema='vsl.startup-rotation-gesture/1',profiles=profiles,envelope=env.tolist(),variation=.035,rotation=rotation,source=str(source),source_sha256=sha(source),seconds=[47.60,48.18],pcm_playback=False,room=False,human_accepted=False)
    save(output/'profile.json',doc)
    save(output/'analysis.json',dict(modes=len(modes),shared_am=am_report,flutter_hz=hz,modal_design_energy_fraction=float(np.sum(mean*ownership)/np.sum(mean)),spectral_widths='Finite-window peak widths mapped to bounded synthetic line widths, not physical damping',pitch='Common acoustic pitch control, no claimed measured shaft RPM',source_seconds=.58,extension='Sustained phase/innovation clock; only 3 spectral states and 9 coarse level controls follow progress; no time-stretched short atom supports'))
    return doc
