"""Estimate a bounded shared high-harmonic phase coordinate, not physical RPM."""
import numpy as np
from scipy import signal


def fit(reference,mean):
    h=len(mean);hz=np.arange(1,h+1)*46.875
    starts=np.arange(0,len(reference)-1024+1,256)
    coefficients=np.array([np.fft.rfft(reference[s:s+1024],axis=0)[1:h+1]*2/1024*
        np.exp(-2j*np.pi*np.arange(1,h+1)*s/1024)[:,None] for s in starts])
    anchor=mean[:,0::2]+1j*mean[:,1::2]
    median=np.median(abs(coefficients),axis=0)
    select=(hz>=1900)&(hz<=8000)
    # Equal bounded contribution per measured line avoids domination by one
    # loud harmonic; weak samples do not give a meaningful phase direction.
    weights=np.clip(abs(coefficients)/np.maximum(median[None,:,:],1e-20),0,1)
    weights*=select[None,:,None]
    weights*=abs(coefficients)>=.25*median[None,:,:]
    phase=np.angle(coefficients*np.conj(anchor)[None,:,:])
    grid=np.linspace(-20e-6,20e-6,321)
    residual=np.cos(phase[None,:,:,:]-2*np.pi*grid[:,None,None,None]*hz[None,None,:,None])
    scores=np.sum(weights[None,:,:,:]*residual,axis=(2,3))
    delay=grid[np.argmax(scores,axis=0)]
    fits=[]
    for parity in (0,1):
        selected=weights.copy();selected[:,np.arange(h)%2!=parity,:]=0
        fits.append(grid[np.argmax(np.sum(selected[None,:,:,:]*residual,axis=(2,3)),axis=0)])
    agreement=float(np.corrcoef(fits)[0,1]) if min(np.std(v) for v in fits)>1e-15 else None
    # Remove slow motion so the candidate does not reintroduce the old
    # several-Hz independent phase wobble. This is an explicit engineering
    # separation, not an identified engine jitter spectrum.
    fast=signal.sosfiltfilt(signal.butter(2,20,fs=187.5,btype='highpass',output='sos'),delay)
    rms=float(np.sqrt(np.mean(fast**2)))
    return dict(delay_seconds=delay,fast_delay_seconds=fast),dict(
        frames=len(starts),selected_hz=[1900,8000],grid_limit_microseconds=20,
        boundary_fraction=float(np.mean(abs(delay)>=19.9e-6)),
        alternating_harmonic_delay_correlation=agreement,
        fast_delay_rms_microseconds=rms*1e6,
        engineering_highpass_hz=20,
        warning='Bounded phase-coordinate fit can contain clock error, source mixing and estimation noise; not measured crank jitter or a validated causal model')


def motion(frames,seed,rms_seconds):
    # Broad stochastic modulation, without one periodic LFO. A genuine
    # bandpass prevents restoring the previously rejected slow phase wobble.
    from scipy.interpolate import CubicSpline
    rng=np.random.default_rng(seed);count=(frames+255)//256+2
    noise=rng.normal(size=count+2048)
    sos=signal.butter(2,[20,70],fs=187.5,btype='bandpass',output='sos')
    impulse=np.zeros(2048);impulse[0]=1
    variance=np.sum(signal.sosfilt(sos,impulse)**2)
    raw=signal.sosfilt(sos,noise)[2048:]/np.sqrt(variance)
    y=CubicSpline(np.arange(count)*256,raw,bc_type='natural')(np.arange(frames))
    # Bounded timing displacement. Scale is a design value guided by the
    # source fit; no per-render RMS or output-loudness normalization.
    return 2*rms_seconds*np.tanh(y/2)
