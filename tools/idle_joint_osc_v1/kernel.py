"""Matched lowpass shape and exact interpolated Gaussian variance."""
import numpy as np
from scipy import signal


def prototype(rate,spacing,taps):
    hz=np.fft.fftfreq(65536,1/rate);f=abs(hz);roll=.5
    lo=spacing*(1-roll)/2;hi=spacing*(1+roll)/2
    power=np.zeros(len(f));power[f<=lo]=1
    middle=(f>lo)&(f<hi);power[middle]=.5*(1+np.cos(np.pi*(f[middle]-lo)/(hi-lo)))
    impulse=np.fft.fftshift(np.fft.ifft(np.sqrt(power)).real)
    start=len(impulse)//2-taps//2;h=impulse[start:start+taps]*signal.windows.kaiser(taps,8.6)
    return h/h.sum()


def weights(fraction):
    r=np.asarray(fraction)
    return np.array([-.5*r+r*r-.5*r**3,1-2.5*r*r+1.5*r**3,
        .5*r+2*r*r-1.5*r**3,-.5*r*r+.5*r**3]).T


def interpolation(h):
    h=np.asarray(h)/np.linalg.norm(h);r=np.arange(96)/96;w=weights(r)
    covariance=np.array([[np.dot(h[:len(h)-abs(i-j)],h[abs(i-j):]) for j in range(4)] for i in range(4)])
    variance=np.einsum('ri,ij,rj->r',w,covariance,w)
    if np.any(variance<=0):raise ValueError('Invalid interpolation variance')
    return h,w/np.sqrt(variance[:,None]),dict(raw_variance_min=float(variance.min()),raw_variance_max=float(variance.max()),
        corrected_variance_error=float(abs(np.einsum('ri,ij,rj->r',w/np.sqrt(variance[:,None]),covariance,w/np.sqrt(variance[:,None]))-1).max()))


def known(spacing):
    native=prototype(48000,spacing,16385);node=prototype(500,spacing,171)
    # Adjacent source-analysis kernels should not carve spectral holes.
    f=np.linspace(-spacing/2,spacing/2,1001);total=np.zeros_like(f)
    for m in range(-3,4):
        _,z=signal.freqz(native,worN=2*np.pi*(f+m*spacing)/48000);total+=abs(z)**2
    ripple=float(10*np.log10(total.max()/total.min()))
    if ripple>.25:raise ValueError(f'Power tile ripple {ripple}dB exceeds declared .25dB')
    _,w,stats=interpolation(node);assert stats['corrected_variance_error']<1e-13
    assert abs(weights(np.linspace(0,1,1001)).sum(axis=1)-1).max()<1e-14
    return dict(power_tile_ripple_db=ripple,interpolation=stats,source_filter_half_support_seconds=8192/48000),native,node
