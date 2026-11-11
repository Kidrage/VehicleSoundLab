"""Observed chirplet-power peaks; no reference interpolation or gap filling."""
import numpy as np
from scipy import signal


def observe(audio, source_start=0):
    # Centered antialias resampling,8kHz. Same80ms/5ms geometry as the old FFT.
    rate=8000;size=640;hop=40;fft=16384
    x=signal.resample_poly(audio,1,6,axis=0,window=('kaiser',8.6))
    starts=np.arange(0,len(x)-size+1,hop)
    hz=np.fft.fftfreq(fft,1/rate);selected=(hz>=35)&(hz<1200)
    window=signal.windows.hann(size,sym=False)
    tau=(np.arange(size)-size/2)/rate
    slopes=np.arange(-2000,2001,250,dtype=float)
    kernel=window[None,:]*np.exp(-1j*np.pi*slopes[:,None]*tau[None,:]**2)
    powers=[]
    for start in starts:
        transformed=np.fft.fft(kernel[:,:,None]*x[start:start+size][None,:,:],n=fft,axis=1)[:,selected]
        power=np.mean(abs(transformed)**2,axis=2)*(2/window.sum())**2
        powers.append(power.max(axis=0))
    return dict(hz=hz[selected],seconds=source_start+(starts+size/2)/rate,
        power_low=np.asarray(powers).T,source_rate=48000,analysis_rate=rate,
        window_samples=size,hop_samples=hop,fft_size=fft,slopes_hz_per_second=slopes.tolist(),
        interpretation='Maximum observed power over explicit chirplet slopes, not an ordinary PSD or confidence probability')
