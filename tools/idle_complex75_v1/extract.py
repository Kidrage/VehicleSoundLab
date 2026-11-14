"""Raw-native relative complex modulation in a supplied acoustic coordinate chart."""
import numpy as np
from scipy import signal
from idle_short_budget_v1.spectral import project

INDICES=np.arange(12000,132000,480)


def lowpass():return signal.firwin(24001,15,fs=48000,window=('kaiser',8.6))


def extract(audio,frequencies,phasors):
    residual,beta=project(np.asarray(audio)[:,None],frequencies,phasors)
    reference=beta[1,0]-1j*beta[14,0]
    if abs(reference)==0:raise ValueError('Unresolved complex75reference')
    h=lowpass();demod=2*residual[:,0]*phasors[:,0].conj()
    filtered=signal.oaconvolve(demod,h,mode='same');b=1+filtered[INDICES]/reference
    if np.any(abs(b)==0) or abs(np.angle(b)).max()>=np.pi-.05:raise ValueError('Unresolved relative complex log chart')
    raw=np.column_stack((np.log(abs(b)),np.angle(b)));mean=raw.mean(axis=0);latent=raw-mean
    return dict(reference=reference,beta=beta,relative_envelope=b,raw_latent=raw,mean=mean,latent=latent,
        native_residual=residual[:,0],filtered=filtered,taps=h)


def response(h,freq):
    t=(np.arange(len(h))-len(h)//2)/48000
    return np.array([np.dot(h,np.exp(-2j*np.pi*f*t)) for f in np.atleast_1d(freq)])
