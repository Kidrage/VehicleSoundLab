"""Spectral fine-structure observations, never a physical noise separator.

All metrics are per-channel. Native Hann grids are used without zero padding.
Whitening divides power by a broad frequency smoother for measurement only.
"""
from dataclasses import dataclass, asdict
import numpy as np
from scipy import signal, ndimage

BANDS = [(1200,3000),(3000,8000),(8000,14000)]


@dataclass(frozen=True)
class TextureSettings:
    window: int = 4096
    hop: int = 256
    envelope_sigma_hz: float = 500
    relative_floor: float = 1e-12
    strongest_lobes: int = 8


def summary(x):
    a=np.asarray(x)
    return dict(p10=float(np.percentile(a,10)),median=float(np.median(a)),p90=float(np.percentile(a,90)))


def distribution(power, relative_floor):
    p=np.maximum(power,0)
    mean=p.mean(axis=0)
    floor=np.maximum(mean*relative_floor,np.finfo(float).tiny)
    p=np.maximum(p,floor[None,:,:])
    total=p.sum(axis=0)
    normalized=p/total[None,:,:]
    entropy=-np.sum(normalized*np.log(normalized),axis=0)
    return dict(flatness=np.exp(np.mean(np.log(p),axis=0))/p.mean(axis=0),
        effective_bin_fraction=np.exp(entropy)/p.shape[0])


def lobe_fraction(power, count=8):
    """Greedy energy in 8 disjoint +/-2-native-bin Hann main-lobe supports.

    This is concentration in fixed supports, not identified sinusoid energy:
    a chirp, AM sideband or noise peak can occupy any of the supports.
    """
    available=np.ones(power.shape,dtype=bool)
    picked=np.zeros(power.shape[1:]);total=power.sum(axis=0)
    channel,frame=np.indices(power.shape[1:])
    for _ in range(count):
        best=np.argmax(np.where(available,power,-1),axis=0)
        for offset in range(-2,3):
            at=best+offset;valid=(at>=0)&(at<len(power))
            at=np.clip(at,0,len(power)-1)
            valid=valid&available[at,channel,frame]
            picked+=np.where(valid,power[at,channel,frame],0)
            available[at,channel,frame]=available[at,channel,frame]&~valid
    return picked/np.maximum(total,np.finfo(float).tiny)


def measure(audio,rate,settings=TextureSettings(),bands=BANDS):
    x=np.asarray(audio)
    if x.ndim!=2 or x.shape[1]!=2 or len(x)<settings.window or not np.isfinite(x).all():
        raise ValueError('Finite stereo and at least one complete window required')
    if not 0<settings.hop<settings.window or rate/2<=max(b[1] for b in bands):raise ValueError('Unsupported analysis rate/window')
    hz,t,z=signal.stft(x,rate,window='hann',nperseg=settings.window,noverlap=settings.window-settings.hop,
        nfft=settings.window,axis=0,boundary=None,padded=False,detrend=False,scaling='psd')
    p=abs(z)**2;df=rate/settings.window
    envelope=ndimage.gaussian_filter1d(p,settings.envelope_sigma_hz/df,axis=0,mode='reflect')
    white=p/np.maximum(envelope,np.maximum(p.mean(axis=0,keepdims=True)*1e-15,np.finfo(float).tiny))
    result=[];series={}
    for lo,hi in bands:
        mask=(hz>=lo)&(hz<hi)
        band=p[mask];q=white[mask]
        raw=distribution(band,settings.relative_floor)
        fine=distribution(q,settings.relative_floor)
        energy=band.sum(axis=0)*2*df
        values=dict(power_dbfs=10*np.log10(np.maximum(energy,np.finfo(float).tiny)),
            flatness=raw['flatness'],effective_bin_fraction=raw['effective_bin_fraction'],
            whitened_flatness=fine['flatness'],whitened_effective_bin_fraction=fine['effective_bin_fraction'],
            strongest_8_lobes_fraction=lobe_fraction(band,settings.strongest_lobes))
        rows={channel:{key:summary(val[c]) for key,val in values.items()} for c,channel in enumerate(['L','R'])}
        result.append(dict(hz=[lo,hi],native_bins=int(mask.sum()),channels=rows,
            below_minus100_dbfs_fraction={ch:float(np.mean(values['power_dbfs'][c]<-100)) for c,ch in enumerate(['L','R'])}))
        series[f'{lo}_{hi}']=values
    return dict(settings=asdict(settings),window_seconds=settings.window/rate,
        native_grid_hz=df,frame_count=len(t),bands=result),dict(seconds=t,values=series)
