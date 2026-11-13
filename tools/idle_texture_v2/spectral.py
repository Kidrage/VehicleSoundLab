"""Minimum-phase spectral resonators; no source waveform or timeline storage."""
import numpy as np
from scipy import ndimage,signal
from scipy.optimize import nnls


def minimum_phase(power, taps):
    # Real cepstrum of the magnitude of a real, even density.
    n=len(power)
    c=np.fft.ifft(.5*np.log(np.maximum(power,1e-30))).real
    causal=np.zeros(n);causal[0]=c[0];causal[1:n//2]=2*c[1:n//2];causal[n//2]=c[n//2]
    return np.fft.ifft(np.exp(np.fft.fft(causal))).real[:taps]


def fit(reference,target,modal_power,plan):
    rate=plan['sample_rate'];n=plan['spectral_grid_frames']
    hz,p=signal.welch(reference[:,0],fs=rate,nperseg=plan['welch_frames'],
        noverlap=plan['welch_frames']-plan['welch_hop'],detrend=False)
    f=np.fft.rfftfreq(n,1/rate)
    # Welch is one-sided density. Convert interior bins back to two-sided.
    two=p.copy();two[1:-1]*=.5
    density=ndimage.gaussian_filter1d(np.interp(f,hz,two),plan['smoothing_hz']/(rate/n))
    kernels=[];responses=[]
    for lo,hi in plan['detail_bands_hz']:
        pad=(hi-lo)*plan['band_padding_fraction']
        weight=np.zeros(len(f));weight[(f>=lo)&(f<=hi)]=1
        left=(f>lo-pad)&(f<lo);right=(f>hi)&(f<hi+pad)
        weight[left]=.5-.5*np.cos(np.pi*(f[left]-(lo-pad))/pad)
        weight[right]=.5+.5*np.cos(np.pi*(f[right]-hi)/pad)
        one=density*weight
        even=np.r_[one,one[-2:0:-1]]
        h=minimum_phase(even,plan['filter_taps']);h/=np.linalg.norm(h)
        actual=abs(np.fft.fft(h,n))**2/n
        freq=np.fft.fftfreq(n,1/rate)
        responses.append([actual[(abs(freq)>=a)&(abs(freq)<b)].sum() for a,b in plan['energy_bands_hz']])
        kernels.append(dict(band_hz=[lo,hi],taps=h.tolist(),right_over_left=1.))
    matrix=np.asarray(responses).T
    weight=1/np.maximum(target[:,0],1e-15)
    squared,_=nnls(matrix*weight[:,None],(target-modal_power)[:,0]*weight)
    for i,model in enumerate(kernels):
        model['gain']=float(np.sqrt(squared[i]))
        j=plan['energy_bands_hz'].index(model['band_hz'])
        model['right_over_left']=float(np.sqrt(target[j,1]/target[j,0]))
    return kernels,dict(response_matrix=matrix.tolist(),predicted_power_L=(modal_power[:,0]+matrix@squared).tolist(),
        stationary_variance=[float(np.dot(k['taps'],k['taps'])) for k in kernels])


def controls():
    # Known minimum-phase transfer has its zero inside the unit circle.
    h=np.array([1.,-.6]);n=65536
    recovered=minimum_phase(abs(np.fft.fft(h,n))**2,128)
    error=float(max(abs(recovered[:2]-h).max(),abs(recovered[2:]).max()))
    assert error<1e-12
    x=np.arange(37,dtype=float)/37
    oracle=np.convolve(x,h)
    assert abs(signal.fftconvolve(x,h)-oracle).max()<1e-12
    parseval=abs(np.sum(abs(np.fft.fft(h,n))**2)/n-np.dot(h,h))
    assert parseval<1e-12
    return dict(minimum_phase_known_filter_error=error,convolution_error=float(abs(signal.fftconvolve(x,h)-oracle).max()),
        stationary_variance_parseval_error=float(parseval))
