"""Short-time phase-conditioned covariance, distinct from a power envelope."""
import numpy as np
from scipy import signal

LAGS=np.arange(-96,97)
BANDS=[[1200,2200],[2200,4000],[4000,8000],[8000,14000]]


def features(z):
    return np.column_stack((z,z[:,1]*z[:,0].conj(),z[:,2]*z[:,0].conj(),z[:,2]*z[:,1].conj()))


def analytic(audio):
    sos=np.array([signal.butter(4,b,btype='bandpass',fs=48000,output='sos') for b in BANDS])
    real=np.column_stack([signal.sosfilt(s,audio[:,0]) for s in sos])
    return signal.hilbert(real,axis=0),sos


def covariance(x,z):
    """All lags share exactly the same feature origins, not varying windows."""
    margin=int(abs(LAGS).max());n=len(x);support=slice(margin,n-margin)
    base=x[support];f=features(z)[support];f=f-f.mean(axis=0)
    out=np.empty((len(LAGS),x.shape[1],f.shape[1]),complex)
    denominator=np.empty((len(LAGS),x.shape[1]))
    for band in range(x.shape[1]):
        power=np.r_[0.,np.cumsum(abs(x[:,band])**2)]
        p0=np.mean(abs(base[:,band])**2)
        late=(power[n-margin+LAGS]-power[margin+LAGS])/(n-2*margin)
        norm=np.sqrt(p0*late);denominator[:,band]=norm
        for k in range(f.shape[1]):
            b=np.zeros(n,complex);b[support]=base[:,band]*f[:,k]
            full=signal.correlate(x[:,band],b,mode='full',method='fft')
            out[:,band,k]=full[n-1+LAGS]/((n-2*margin)*norm)
    return out,denominator


def known():
    n=49152;rate=48000;t=np.arange(n)/rate
    # The common support has exactly three modulation cycles.
    w=2*np.pi*(3*rate/(n-192));v=2*np.pi*(1000*rate/(n-192));a=.42
    z=np.column_stack([np.exp(1j*w*t),np.exp(2j*w*t),np.exp(3j*w*t)])
    x=((1+a*np.cos(w*t))*np.exp(1j*v*t))[:,None]
    c,_=covariance(x,z)
    expected=a/2*np.exp(1j*v*LAGS/rate)*(1+np.exp(1j*w*LAGS/rate))/(1+a*a/2)
    err=float(abs(c[:,0,0]-expected).max());assert err<2e-13
    carrier,_=covariance(np.exp(1j*v*t)[:,None],z)
    zero=float(abs(carrier).max());assert zero<2e-13
    pair=[]
    for phase in [-.9,.9]:
        wave=np.exp(1j*v*t)*(1+a*np.exp(1j*phase)*np.cos(w*t))
        pair.append(covariance(wave[:,None],z)[0][:,0,0])
    same0=float(abs(pair[0][96]-pair[1][96]));different=float(abs(pair[0]-pair[1]).max())
    assert same0<2e-13 and different>1e-3
    return dict(all193_AM_lag_error=err,pure_carrier_cyclic_absmax=zero,
        same_magnitude_spectrum_three_tone_pair=True,pair_zero_lag_difference=same0,
        pair_nonzero_lag_absmax_difference=different),dict(x=x,z=z,c=c,pair=np.array(pair))
