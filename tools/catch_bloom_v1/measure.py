"""Fixed-window mixed-recording power, with no phase/RPM inference."""
import numpy as np
from scipy import signal
BANDS=((30,120),(120,300),(300,600))
RATE=48000
def spectrum(x):
    f,t,p=signal.spectrogram(x,RATE,window='hann',nperseg=4800,noverlap=4320,
        detrend=False,scaling='density',axis=0,mode='psd')
    return f,t,p
def powers(x):
    f,t,p=spectrum(x)
    return t,np.array([p[(f>=lo)&(f<hi)].sum(axis=0).mean(axis=0)*10 for lo,hi in BANDS]).T
def coefficients(hz,q):
    # scipy's independent peak-normalized digital resonator formulation.
    return signal.iirpeak(hz,q,fs=RATE)
def rbj(hz,q):
    # Runtime uses RBJ bandwidth alpha=sin(w)/(2Q), not scipy's tan(BW/2).
    w=2*np.pi*hz/RATE;alpha=np.sin(w)/(2*q)
    return np.array([alpha,0,-alpha])/(1+alpha),np.array([1,-2*np.cos(w)/(1+alpha),(1-alpha)/(1+alpha)])
def pulse(u,p,q):
    y=np.zeros_like(np.asarray(u,dtype=float));inside=(u>0)&(u<1);at=p/(p+q)
    y[inside]=np.exp(p*np.log(u[inside]/at)+q*np.log((1-u[inside])/(1-at)))
    return y
def envelope(progress,gate,p,q):
    # Non-RT fit oracle. C's exponential follower is independently checked.
    target=np.where(gate,pulse(progress,p,q),0);out=np.zeros_like(target);state=0.
    attack=-np.expm1(-1/(RATE*.005));release=-np.expm1(-1/(RATE*.035))
    for n,value in enumerate(target):
        state+=(attack if value>state else release)*(value-state);out[n]=state
    return out
def band_gram(components,first,stop):
    """Coherent component Gram per broad band; includes all cross terms."""
    # Shape = [component,sample,channel], full interval Welch for stable means.
    values=[]
    for x in components:
        f,t,z=signal.stft(x[first:stop],RATE,nperseg=4800,noverlap=2400,
            detrend=False,scaling='psd',boundary=None,padded=False,axis=0)
        values.append(z)
    z=np.asarray(values);rows=[]
    for lo,hi in BANDS:
        selected=z[:,(f>=lo)&(f<hi)]
        # Real signals, non-DC/non-Nyquist: factor2, then df=10Hz.
        rows.append(np.einsum('ifct,jfct->ij',selected,selected.conj()).real*20/(z.shape[2]*z.shape[3]))
    return np.array(rows)
