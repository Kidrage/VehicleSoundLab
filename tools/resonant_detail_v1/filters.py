"""Stable noise-driven AR resonators and an independent expected-PSD budget."""
import numpy as np
from scipy import linalg,ndimage,signal
from .envelope import samples

def spectral_matrix_operator(power,plan):
    # Expected 2048-Hann Welch measurement, including window convolution and
    # its native24Hz bins. Input is a two-sided density on the finer grid.
    n=len(power);size=2048;window=signal.windows.hann(size,sym=False)
    kernel=abs(np.fft.fft(window,n))**2;kernel/=kernel.sum()
    smooth=np.fft.ifft(np.fft.fft(power)*np.fft.fft(kernel)).real
    indices=np.arange(size//2+1)*(n//size)
    one=smooth[indices].copy();one[1:-1]*=2
    hz=np.fft.rfftfreq(size,1/plan['sample_rate'])
    return np.array([one[(hz>=a)&(hz<b)].sum()*plan['sample_rate']/size for a,b in plan['bands_hz']])

def theory(a,sos,beta,plan):
    n=plan['spectral_grid_frames'];rate=plan['sample_rate']
    w=2*np.pi*np.arange(n)/n
    _,h=signal.freqz([1],a,worN=w)
    raw=abs(h)**2/rate
    # Fix one innovation scale per model from its theoretical stationary
    # variance, never from any generated clip or seed.
    sigma=1/np.sqrt(raw.sum()*rate/n);raw*=sigma*sigma
    envelope=samples(beta,plan['cycle_frames'])
    e=np.fft.fft(envelope)/len(envelope);modulated=np.zeros(n)
    for k,weight in enumerate(abs(e)**2):
        if weight>1e-18:modulated+=weight*np.roll(raw,k*(n//len(e)))
    _,post=signal.sosfreqz(sos,worN=w)
    return modulated*abs(post)**2,float(sigma)

def fit(reference,plan,envelopes):
    n=plan['spectral_grid_frames'];rate=plan['sample_rate'];order=plan['AR_order']
    hz,power=signal.welch(reference[:,0],fs=rate,nperseg=2048,noverlap=1536,detrend=False)
    freq=np.fft.rfftfreq(n,1/rate)
    measured=np.interp(freq,hz,power)
    measured=ndimage.gaussian_filter1d(measured,plan['source_spectrum_smoothing_hz']/(rate/n))
    models=[]
    for (low,high),envelope in zip(plan['bands_hz'],envelopes):
        pad=(high-low)*plan['band_padding_fraction'];edge=[low-pad,high+pad]
        weight=np.zeros(len(freq));inside=(freq>=low)&(freq<=high);weight[inside]=1
        left=(freq>edge[0])&(freq<low);right=(freq>high)&(freq<edge[1])
        weight[left]=.5-.5*np.cos(np.pi*(freq[left]-edge[0])/pad)
        weight[right]=.5+.5*np.cos(np.pi*(freq[right]-high)/pad)
        covariance=np.fft.irfft(measured*weight,n)
        covariance/=covariance[0]
        covariance[0]+=plan['AR_diagonal_ridge']
        a=np.r_[1,linalg.solve_toeplitz(covariance[:order],-covariance[1:order+1])]
        radius=float(max(abs(np.roots(a))))
        if radius>=plan['maximum_pole_radius']:raise ValueError(f'Unqualified AR stability: {low}, {radius}')
        sos=signal.butter(plan['post_bandpass_order'],edge,fs=rate,btype='bandpass',output='sos')
        psd,sigma=theory(a,sos,envelope['coefficients'],plan)
        models.append(dict(band_hz=[low,high],a=a.tolist(),sos=sos.tolist(),sigma=sigma,
            pole_radius=radius,envelope=envelope,theoretical_band_power=spectral_matrix_operator(psd,plan).tolist()))
    return models
