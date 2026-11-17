"""Acoustic-only peaks/envelopes; no identification of physical engine parts."""
import numpy as np
from scipy import signal
from .band_scope import normalize,edges,mask

EDGES=((60,300),(300,1200),(1200,4500),(4500,14000))


def spectrum(x):
    f,p=signal.welch(x,48000,nperseg=min(2048,len(x)),axis=0,detrend=False)
    return f,p.mean(axis=1)


def observe(x,background,analysis_scope=None):
    scope=normalize(analysis_scope);scoped=scope['mode']=='band'
    f,p=spectrum(x);fb,bp=spectrum(background)
    bp=np.interp(f,fb,bp);excess=np.maximum(0,p-bp)
    # Modal peaks are measurements of a mixed recording, not extracted cylinders.
    peaks,_=signal.find_peaks(10*np.log10(np.maximum(excess,1e-30)),prominence=3,distance=3)
    eligible=mask(f,scope)
    peaks=[int(k) for k in sorted(peaks,key=lambda k:excess[k],reverse=True)
           if (eligible[k] if scoped else 40<=f[k]<=9000)][:12]
    channel=int(np.argmax(np.mean(x*x,axis=0)));clock=np.arange(len(x))/48000
    modal=[]
    for k in peaks:
        logs=np.log(np.maximum(excess[k-1:k+2],1e-30));den=logs[0]-2*logs[1]+logs[2]
        offset=float(np.clip(.5*(logs[0]-logs[2])/den,-.5,.5)) if den else 0
        hz_refined=float(f[k]+offset*(f[1]-f[0]))
        if scoped:hz_refined=float(np.clip(hz_refined,scope['low_hz'],np.nextafter(scope['high_hz'],scope['low_hz'])))
        coefficient=np.sum(x[:,channel]*signal.windows.hann(len(x),sym=False)*np.exp(-2j*np.pi*hz_refined*clock))
        modal.append(dict(hz=hz_refined,phase=float(np.angle(coefficient)+np.pi/2),phase_channel=channel,
                          frequency_bin_hz=float(f[1]-f[0])))
    from .short_time import layout,LONG_MIN_FRAMES
    window,overlap=layout(len(x))
    hz,t,z=signal.stft(x,48000,nperseg=window,noverlap=overlap,axis=0,boundary=None,padded=False)
    power=(abs(z)**2).mean(axis=1)
    bands=[]
    for lo,hi in edges(scope,EDGES):
        curve=power[(hz>=lo)&(hz<hi)].sum(axis=0)
        bg=float(bp[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]))
        # STFT 'spectrum' energy is scaled back with Hann ENBW (1.5 bins).
        curve=curve*2/1.5
        energy=np.maximum(curve-bg,0);peak=int(np.argmax(energy));best=float(energy[peak]);tail=(np.arange(len(t))>=peak)&(energy>best*.1)
        tau=.08;slope=None
        if tail.sum()>=3 and best>1e-20:
            slope=float(np.polyfit(t[tail],.5*np.log(np.maximum(energy[tail],1e-30)),1)[0])
            if slope<0:tau=float(np.clip(-1/slope,.008,2))
        above=np.flatnonzero(energy>=best*.1);high=np.flatnonzero(energy>=best*.9)
        attack=float(np.clip(t[high[0]]-t[above[0]],.0005,.08)) if len(high) and len(above) else .003
        bands.append(dict(hz=[lo,hi],background_power=bg,excess_power=float(excess[(f>=lo)&(f<hi)].sum()*(f[1]-f[0])),
            peak_time=float(t[peak]),attack_seconds=attack,decay_seconds=tau,log_amplitude_tail_slope=slope,
            decay_fitted=bool(slope is not None and slope<0)))
    rms=np.sqrt(np.mean(x*x,axis=0));bg_rms=np.sqrt(np.mean(background*background,axis=0))
    report=dict(rms_channels=rms.tolist(),background_rms_channels=bg_rms.tolist(),
        excess_mean_square=float(max(0,np.mean(rms*rms)-np.mean(bg_rms*bg_rms))),
        event_to_background_db=float(10*np.log10(max(np.mean(rms*rms),1e-30)/max(np.mean(bg_rms*bg_rms),1e-30))),
        modal_peaks_hz=[float(f[k]) for k in peaks],modal_observations=modal,bands=bands,
        limits=['PSD background subtraction is a statistical excess estimate, not waveform source separation.',
                'Decay is a bounded acoustic fit; nondecreasing/too-short tails use explicitly marked engineering fallback.',
                'One mixed recording does not establish mechanical identity, RPM, dry physical source or source position.'])
    if len(x)<LONG_MIN_FRAMES:
        report['time_analysis']=dict(mode='short-event-v1',window_frames=window,hop_frames=window-overlap,
            frequency_bin_hz=48000/window,event_frames=len(x),
            limitation='Short-window low-frequency and decay estimates are unresolved or fallback; no physical source identification.')
    if scoped:
        selected=mask(f,scope);df=f[1]-f[0]
        ep=float(p[selected].sum()*df);background_power=float(bp[selected].sum()*df)
        report.update(analysis_scope=scope,scoped_event_power=ep,scoped_background_power=background_power,
            scoped_excess_mean_square=max(0,ep-background_power),
            scoped_positive_psd_excess_power=float(excess[selected].sum()*df),
            scoped_event_to_background_db=float(10*np.log10(max(ep,1e-30)/max(background_power,1e-30))))
        report['limits'].append('Frequency scope measures an acoustic increment only; SOS output is not a brickwall-isolated physical source.')
    return report,(f,p,bp,excess,peaks,t,power)
