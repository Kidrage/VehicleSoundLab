"""Offline waveform prediction in a supplied observed-phase coordinate.

No RPM inference, physical source separation or recovered audio export.
Train cycles precede held-out cycles; phase/frequency is supplied over the
whole interval, so this is conditional waveform prediction, not online pitch
prediction. Both microphone channels use the exact same time map.
"""
from dataclasses import dataclass,asdict
import numpy as np
from scipy import signal

@dataclass(frozen=True)
class CycleSettings:
    train_cycles:int=8
    test_cycles:int=4
    upsampling:int=16
    trim_seconds:float=.04

def phase_grid(audio,rate,times,frequency,divisor=1,origin=0,settings=CycleSettings()):
    x=np.asarray(audio,dtype=float);t=np.asarray(times,dtype=float);f=np.asarray(frequency,dtype=float)/divisor
    if x.ndim!=2 or x.shape[1]!=2 or t.ndim!=1 or len(t)<3 or t.shape!=f.shape:
        raise ValueError('Stereo samples and a supplied phase-rate path required')
    if not np.isfinite(x).all() or not np.isfinite(t).all() or not np.isfinite(f).all() or np.any(np.diff(t)<=0) or np.min(f)<=0:
        raise ValueError('Finite increasing time and positive phase rate required')
    if rate<16000 or divisor<1 or settings.upsampling<4 or t[0]<origin or t[-1]>origin+(len(x)-1)/rate:
        raise ValueError('Invalid bounds/rate/divisor')
    if settings.train_cycles<1 or settings.test_cycles<1:raise ValueError('Positive train/test lengths required')
    # Integrate the supplied piecewise-linear frequency exactly. Inversion is
    # queried on a native-rate time grid before the dense waveform interpolator.
    first=int(np.ceil((t[0]-origin)*rate));last=int(np.floor((t[-1]-origin)*rate))
    source_time=origin+np.arange(first,last+1)/rate
    path_cycles=np.r_[0,np.cumsum((f[:-1]+f[1:])*np.diff(t)/2)]
    j=np.clip(np.searchsorted(t,source_time,side='right')-1,0,len(t)-2)
    dt=source_time-t[j];slope=(f[j+1]-f[j])/(t[j+1]-t[j])
    cycles=path_cycles[j]+f[j]*dt+.5*slope*dt*dt
    keep=(source_time>=t[0]+settings.trim_seconds)&(source_time<=t[-1]-settings.trim_seconds)
    if not keep.any():raise ValueError('Interval too short for trim')
    start=int(np.ceil(cycles[keep][0]));stop=int(np.floor(cycles[keep][-1]));count=stop-start
    if count<settings.train_cycles+settings.test_cycles:raise ValueError('Insufficient complete cycles')
    # Never subsample relative to original sample density, even at the slowest
    # portion of the supplied path. Equal phase steps are NOT equal raw-time steps.
    bins=int(np.ceil(rate/np.min(f)))
    requested=start+np.arange(count*bins)/bins
    inverse=np.interp(requested,cycles,source_time)
    guard=round(.04*rate);a=max(0,first-guard);b=min(len(x),last+guard+1)
    dense=signal.resample_poly(x[a:b],settings.upsampling,1,axis=0,window=('kaiser',8.6),padtype='line')
    index=(inverse-origin-a/rate)*rate*settings.upsampling
    result=np.column_stack([np.interp(index,np.arange(len(dense)),dense[:,c]) for c in range(2)])
    grid=result.reshape(count,bins,2)
    return grid,dict(cycle_count=count,bins_per_cycle=bins,divisor=divisor,
        observed_frequency_hz=[float(np.min(f*divisor)),float(np.max(f*divisor))],
        supplied_interval_seconds=[float(t[0]),float(t[-1])],
        kept_source_seconds=[float(inverse[0]),float(inverse[-1])],
        normalized_mean_square_policy='Equal phase samples; not original-time power or physical noise fraction',
        interpolation=f'Piecewise-linear supplied frequency integrated analytically; native inverse lookup; {settings.upsampling}x Kaiser and linear waveform lookup',
        settings=asdict(settings)),inverse.reshape(count,bins)

def predict(grid,settings=CycleSettings()):
    x=np.asarray(grid);n,p,c=x.shape
    if c!=2 or n<settings.train_cycles+settings.test_cycles or not np.isfinite(x).all():raise ValueError('Insufficient finite stereo cycles')
    actual=[];error=[];folds=[]
    for first in range(settings.train_cycles,n-settings.test_cycles+1,settings.test_cycles):
        template=x[first-settings.train_cycles:first].mean(axis=0)
        test=x[first:first+settings.test_cycles]
        residual=test-template[None,:,:]
        actual.append((test*test).sum(axis=(0,1)));error.append((residual*residual).sum(axis=(0,1)))
        folds.append(dict(train_cycle_indices=[first-settings.train_cycles,first],test_cycle_indices=[first,first+settings.test_cycles]))
    actual=np.sum(actual,axis=0);error=np.sum(error,axis=0)
    ratios=error/np.maximum(actual,np.finfo(float).tiny)
    return dict(error_to_signal_db_lr=(10*np.log10(np.maximum(ratios,1e-30))).tolist(),
        held_out_cycle_count=len(folds)*settings.test_cycles,folds=folds,
        interpretation='Squared future waveform error relative to the actual held-out waveform in equal-phase coordinates. Negative means small error. Positive values are valid. Not explained-energy, noise percentage or realism score.')

def band_prediction(audio,rate,times,frequency,divisors=(1,2,5,10),origin=0,bands=((300,1200),(1200,3000),(3000,8000)),settings=CycleSettings()):
    rows=[]
    for lo,hi in bands:
        # Identical causal Butterworth analysis filters for both channels. Full
        # supplied audio is filtered before cropping the analysis interval.
        sos=signal.butter(4,[lo,hi],btype='bandpass',fs=rate,output='sos')
        filtered=signal.sosfilt(sos,audio,axis=0)
        for divisor in divisors:
            try:
                grid,meta,_=phase_grid(filtered,rate,times,frequency,divisor,origin,settings)
                result=predict(grid,settings)
                rows.append(dict(band_hz=[lo,hi],divisor=divisor,status='measured',grid=meta,**result))
            except ValueError as e:
                rows.append(dict(band_hz=[lo,hi],divisor=divisor,status='unmeasured',reason=str(e)))
    return rows
