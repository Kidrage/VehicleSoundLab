"""Deterministic meter controls, never engine presets."""
import numpy as np


def fixtures():
    N=16384
    for name in ('mono','inverted_mono','unequal_phase','silent_right','zero','correlated_noise_AM','weak_HF','native48k'):
        rate=48000 if name=='native48k' else 65536
        t=np.arange(N)/rate
        if name=='native48k':frequencies=np.array([40,350,600,760,1020,1550])*rate/4096
        else:frequencies=64*np.array([5,65,110,140,185,300])
        audio=np.zeros((N,2))
        for h,f in enumerate(frequencies):
            a=.12/(1+.3*h)
            angle=2*np.pi*f*t+.17*h
            audio[:,0]+=a*np.cos(angle)
            audio[:,1]+=.53*a*np.cos(angle+.3+.07*h)
        if name=='mono':audio[:,1]=audio[:,0]
        if name=='inverted_mono':audio[:,1]=-audio[:,0]
        if name=='silent_right':audio[:,1]=0
        if name=='zero':audio[:]=0
        if name=='correlated_noise_AM':
            rng=np.random.default_rng(379811);noise=rng.normal(0,.014,(N,2))
            noise[:,1]=.6*noise[:,0]+.8*noise[:,1]
            audio=audio*(1+.23*np.cos(2*np.pi*7*t))[:,None]+noise
        if name=='weak_HF':
            audio[:,0]=1e-13*np.cos(2*np.pi*19200*t)
            audio[:,1]=.7e-13*np.cos(2*np.pi*19200*t+.37)
            # Known tiny broadband content keeps every diagnostic band real,
            # rather than testing normalized phase of FFT roundoff alone.
            audio+=np.random.default_rng(703917).normal(0,1e-15,audio.shape)
        if name=='unequal_phase':
            audio[:,0]+=.013+.006*(-1.)**np.arange(N)
            audio[:,1]+=.011+.002*(-1.)**np.arange(N)
        yield name,audio,rate
