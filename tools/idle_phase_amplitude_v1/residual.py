"""Project resolved coherent lines before estimating the low detail spectral shape."""
import numpy as np
from scipy import signal,ndimage
from idle_texture_v2.spectral import minimum_phase


def design(frames,frequencies,phasors):
    t=np.arange(frames)/48000;z=np.exp(2j*np.pi*t[:,None]*frequencies)
    z[:,[1,2,4]]=phasors
    return np.column_stack((z.real,z.imag,np.ones(frames)))


def project(audio,frequencies,phasors):
    A=design(len(audio),frequencies,phasors);lo,hi=12000,len(audio)-12000
    w=signal.windows.hann(hi-lo,sym=False)
    gram=A[lo:hi].T@(A[lo:hi]*w[:,None])
    beta=np.linalg.solve(gram,A[lo:hi].T@(audio[lo:hi]*w[:,None]))
    residual=audio[lo:hi]-A[lo:hi]@beta
    return residual,beta


def filters(residual,bands):
    hz,power=signal.welch(residual[:,0],fs=48000,nperseg=24000,noverlap=12000,detrend=False)
    power[1:-1]*=.5;f=np.fft.rfftfreq(65536,1/48000)
    density=ndimage.gaussian_filter1d(np.interp(f,hz,power),8/(48000/65536))
    result=[]
    for lo,hi in bands:
        pad=(hi-lo)*.1;weight=np.zeros(len(f));weight[(f>=lo)&(f<=hi)]=1
        left=(f>lo-pad)&(f<lo);right=(f>hi)&(f<hi+pad)
        weight[left]=(.5-.5*np.cos(np.pi*(f[left]-lo+pad)/pad))
        weight[right]=(.5+.5*np.cos(np.pi*(f[right]-hi)/pad))
        one=density*weight;h=minimum_phase(np.r_[one,one[-2:0:-1]],8192);h/=np.linalg.norm(h)
        result.append(h)
    return np.array(result)


def known():
    frequencies=np.array([37.19,75.31,112.73,150.12,187.69,225.43,262.77,284.61,299.84,359.43,375.16,472.63,486.93])
    t=np.arange(144000)/48000;theta=2*np.pi*t[:,None]*frequencies
    theta[:,[1,2,4]]-=np.array([.9,1.2,.7])/[1.6,1.3,1.1]*np.cos(2*np.pi*t[:,None]*[1.6,1.3,1.1])
    z=np.exp(1j*theta[:,[1,2,4]]);A=design(len(t),frequencies,z)
    coefficient=np.random.default_rng(41791).normal(0,.02,(27,2))
    audio=A@coefficient;residual,beta=project(audio,frequencies,z)
    error=float(abs(residual).max());assert error<1e-12
    # Real AM and an omitted neighbor survive this constant-coefficient projection.
    extra=.02*np.cos(theta[:,1])*np.cos(2*np.pi*.8*t)+.01*np.cos(2*np.pi*(frequencies[1]+8)*t)
    contaminated=audio+extra[:,None];left,_=project(contaminated,frequencies,z)
    rms=float(np.sqrt(np.mean(left**2)));assert rms>.003
    return dict(exact_moving_modal_residual_error_FS=error,unmodeled_AM_neighbor_residual_rms=rms,
                constant_projection_is_not_complete_source_separation=True)
