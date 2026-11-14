"""Offline transient observations; these do not separate a physical source."""
import numpy as np
from scipy import ndimage,signal

def observe(audio,plan):
    size,hop=plan['frame_size'],plan['hop'];rate=plan['audio_rate']
    window=signal.windows.hann(size,sym=False)
    frames=np.lib.stride_tricks.sliding_window_view(audio,size,axis=0)[::hop]
    z=np.fft.rfft(frames*window[None,None,:],axis=-1).transpose(0,2,1)
    psd=(z.conj()*z).real/(rate*sum(window*window));psd[:,1:-1]*=2
    csd=z[:,:,1]*z[:,:,0].conj()/(rate*sum(window*window));csd[:,1:-1]*=2
    hz=np.fft.rfftfreq(size,1/rate)
    bands=np.stack([psd[:,(hz>=lo)&(hz<hi)].sum(axis=1)*rate/size for lo,hi in plan['bands_hz']],axis=1)
    cross=np.stack([csd[:,(hz>=lo)&(hz<hi)].sum(axis=1)*rate/size for lo,hi in plan['bands_hz']],axis=1)
    settings=plan['candidate_detection'];mono=bands.mean(axis=2)
    baseline=ndimage.median_filter(mono,size=(settings['median_context_frames'],1),mode='nearest')
    excess=10*np.log10(np.maximum(mono,1e-30)/np.maximum(baseline,1e-30))
    # The second largest of three band excesses implements the declared two-band requirement.
    selected=excess[:,settings['bands']]
    score=np.sort(selected,axis=1)[:,-settings['minimum_bands']]
    peaks,_=signal.find_peaks(score,height=settings['minimum_above_local_median_db'],
        distance=round(settings['minimum_spacing_seconds']*rate/hop))
    return dict(time=(np.arange(len(frames))*hop+size/2)/rate,bands=bands,cross=cross,
        rms=np.sqrt(np.mean(frames**2,axis=2)),crest=np.max(abs(frames),axis=2)/np.maximum(np.sqrt(np.mean(frames**2,axis=2)),1e-30),
        excess=excess,score=score,peaks=peaks)

def controls(plan):
    rate=plan['audio_rate'];time=np.arange(3*rate)/rate
    a=.1*np.sin(2*np.pi*2400*time)+.04*np.sin(2*np.pi*4800*time)
    steady=observe(np.column_stack((a,.7*a)),plan)
    assert len(steady['peaks'])==0
    rng=np.random.default_rng(160011);audio=rng.normal(size=(len(time),2))*.003
    first=int(1.475*rate);count=int(.05*rate)
    audio[first:first+count]+=rng.normal(size=(count,2))*.15*np.hanning(count)[:,None]
    pulse=observe(audio,plan);times=pulse['time'][pulse['peaks']]
    assert len(times)==1 and abs(times[0]-1.5)<.04
    return dict(steady_false_candidates=0,pulse_candidates=times.tolist(),pulse_maximum_excess_db=float(pulse['score'].max()))
