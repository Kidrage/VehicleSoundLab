"""Conventional descriptive measurements and root candidates, not physical RPM."""
import numpy as np
import soundfile as sf
from scipy import signal


def root_candidates(audio,rate,lo=20,hi=400):
    n=min(len(audio),max(2048,int(rate*.25)))
    frame=audio[:n]-audio[:n].mean(axis=0)
    # Sum channel powers/correlations; do not cancel out-of-phase stereo.
    fft=1<<int(np.ceil(np.log2(2*n)))
    power=np.sum(abs(np.fft.rfft(frame*signal.windows.hann(n)[:,None],n=fft,axis=0))**2,axis=1)
    ac=np.fft.irfft(power,n=fft)[:n]
    ac/=max(float(ac[0]),1e-30)
    peaks=signal.find_peaks(ac)[0]
    peaks=peaks[(peaks>=int(rate/hi))&(peaks<=min(n-2,int(rate/lo)))]
    peaks=sorted(peaks,key=lambda j:ac[j],reverse=True)[:8]
    result=[]
    for j in peaks:
        a,b,c=ac[j-1:j+2];den=a-2*b+c
        delta=np.clip(.5*(a-c)/den,-.5,.5) if den else 0.
        result.append(dict(hz=float(rate/(j+delta)),score=float(ac[j])))
    return result


def measure(audio,rate,root_hint=None):
    if audio.ndim!=2 or audio.shape[1] not in (1,2) or not np.isfinite(audio).all():
        raise ValueError('需要有限数值的单声道或双声道音频')
    if len(audio)<rate*.4 or len(audio)>rate*60:
        raise ValueError('请使用0.4–60秒的已裁剪片段')
    candidates=root_candidates(audio,rate)
    root=float(root_hint) if root_hint else (candidates[0]['hz'] if candidates else None)
    frequencies,psd=signal.welch(audio,rate,nperseg=min(8192,len(audio)),axis=0)
    power=psd.sum(axis=1)
    bands=[]
    for lo,hi in ((20,80),(80,250),(250,1000),(1000,3000),(3000,6000),(6000,10000),(10000,20000)):
        selected=(frequencies>=lo)&(frequencies<min(hi,rate/2))
        value=float(np.trapezoid(power[selected],frequencies[selected])) if selected.sum()>1 else 0.
        bands.append(dict(low=lo,high=hi,power=value,db=10*np.log10(max(value,1e-20))))
    centers=np.linspace(.15,len(audio)/rate-.15,min(80,max(3,int(len(audio)/rate*10))))
    track=[]
    for t in centers:
        first=max(0,int((t-.125)*rate));stop=min(len(audio),first+int(.25*rate))
        options=root_candidates(audio[first:stop],rate)
        if root and options:
            close=[v for v in options if .65*root<v['hz']<1.55*root]
            if close:
                selected=max(close,key=lambda v:v['score']-.1*abs(np.log(v['hz']/root)))
                track.append(dict(seconds=float(t),**selected))
    hz=np.array([v['hz'] for v in track])
    drift=float((np.percentile(hz,90)-np.percentile(hz,10))/root) if len(hz)>2 and root else None
    step=max(1,len(audio)//800)
    peaks=np.max(abs(audio[:len(audio)//step*step].reshape(-1,step,audio.shape[1])),axis=1)
    stereo=float(np.corrcoef(audio.T)[0,1]) if audio.shape[1]==2 and np.min(np.std(audio,axis=0))>1e-12 else None
    return dict(seconds=len(audio)/rate,rate=rate,channels=audio.shape[1],
                peak=float(np.max(abs(audio))),rms_dbfs=float(20*np.log10(max(np.sqrt(np.mean(audio**2)),1e-12))),
                root_candidates=candidates,root_hz=root,pitch_track=track,pitch_drift=drift,
                stereo_correlation=stereo,bands=bands,waveform=peaks.max(axis=1).tolist(),
                spectrum_hz=frequencies[::4].tolist(),spectrum_db=(10*np.log10(np.maximum(power[::4],1e-20))).tolist(),
                root_meaning='声学周期候选，需要确认；不自动推断气缸数、RPM、负载或录音位置',
                stable_candidate=bool(root and drift is not None and drift<.05))
