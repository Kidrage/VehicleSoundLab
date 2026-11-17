"""Portable parameter contract and independent NumPy/SciPy audition model."""
import math
import numpy as np
from scipy import signal

from .contract import KINDS,validate


def randoms(seed,count):
    state=seed or 0x97bd5821;values=np.empty(count)
    for i in range(count):
        state^=(state<<13)&0xffffffff;state^=state>>17;state^=(state<<5)&0xffffffff
        values[i]=2*(state/4294967296)-1
    return values


def coefficients(hz,q):
    w=2*np.pi*hz/48000;a=np.sin(w)/(2*q);den=1+a
    return np.array([a/den,0,-a/den]),np.array([1,-2*np.cos(w)/den,(1-a)/den])


def attack(t,seconds):
    x=np.minimum(1,t/seconds) if seconds else np.ones_like(t)
    return x*x*(3-2*x)


def synth(p,seed=27431,pitch=1,decay=1,texture=1,strength=1,seconds=None,release_at=None):
    validate(p);duration=math.ceil(p['duration_seconds']*decay*48000)
    frames=duration if seconds is None else min(duration,round(seconds*48000))
    t=np.arange(frames)/48000;r=randoms(seed,frames+1);variation=1+.002*r[0];x=np.zeros(frames)
    def contour(hz):
        return next((np.interp(t/decay,c['seconds'],c['gain']) for c in p.get('contours',[]) if c['low_hz']<=hz<c['high_hz']),None)
    for m in p['modes']:
        frequency=np.full(frames,min(21000,m['hz']*pitch*variation))
        if p['sweep_seconds']:
            end=min(21000,m['end_hz']*pitch*variation)
            frequency+=(end-frequency)*np.minimum(1,t/(p['sweep_seconds']*decay))
        phase=m['phase']+2*np.pi*np.concatenate(([0.],np.cumsum(frequency[:-1])))/48000
        env=contour(m['hz'])
        if env is None:
            env=1 if p['gated'] else np.exp(-t/(m['decay_seconds']*decay))
            if m.get('attack_seconds',0):env=env*attack(t,m['attack_seconds'])
        x+=m['amplitude']*env*np.sin(phase)
    noise=np.zeros(frames) if p.get('noise_lowpass_hz',0) else None
    for b in p['bands']:
        num,den=coefficients(min(21000,b['hz']*pitch),b['q'])
        env=contour(b['hz'])
        if env is None:
            env=attack(t,b['attack_seconds'])
            if not p['gated']:env=env*np.exp(-t/(b['decay_seconds']*decay))
        component=b['amplitude']*texture*env*signal.lfilter(num,den,r[1:])
        if noise is None:x+=component
        else:noise+=component
    if noise is not None:
        cutoff=min(21000,p['noise_lowpass_hz']*pitch)
        x+=signal.sosfilt(signal.butter(4,cutoff,fs=48000,output='sos'),noise)
    env=attack(t,p['attack_seconds']);left=np.minimum(1,(duration-np.arange(frames))/(48000*p['release_seconds']))
    env*=left*left*(3-2*left)
    if release_at is not None:
        left=np.clip(1-(t-release_at)/p['release_seconds'],0,1);env*=left*left*(3-2*left)
    return x*env*p['level']*strength
