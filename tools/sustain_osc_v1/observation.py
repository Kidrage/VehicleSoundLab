"""Relative acoustic-coordinate observation, never measured engine RPM."""
import numpy as np
from scipy import signal


def ridge(audio,rate,seconds,window_seconds):
    n=round(window_seconds*rate);n+=n%2
    win=signal.windows.hann(n,sym=False);fft=n*8
    frequencies=np.fft.rfftfreq(fft,1/rate)
    selected=(frequencies>220)&(frequencies<285)
    path=[]
    for t in seconds:
        c=round(t*rate);frame=audio[c-n//2:c+n//2]
        if len(frame)!=n:raise ValueError('Unsupported edge')
        z=np.fft.rfft(frame*win[:,None],n=fft,axis=0)
        power=np.sum(abs(z)**2,axis=1)
        peaks=signal.find_peaks(10*np.log10(power+1e-30),prominence=5)[0]
        peaks=peaks[selected[peaks]]
        if not len(peaks):raise ValueError('Missing relative ridge; no invented continuation')
        k=peaks[np.argmax(power[peaks])]
        q=np.log(power[k-1:k+2]+1e-30)
        delta=.5*(q[0]-q[2])/(q[0]-2*q[1]+q[2])
        path.append((k+np.clip(delta,-.5,.5))*rate/fft)
    return np.asarray(path)


def normalize(audio,rate,seconds,ridge_hz,divisor=5,cycle_samples=1024):
    # Retain input stereo; filter only this explicitly labelled derivative.
    taps=signal.firwin(1025,[80,14000],pass_zero=False,fs=rate,window=('kaiser',12))
    band=signal.fftconvolve(audio,taps[:,None],mode='same',axes=0)
    source_t=np.arange(round(seconds[0]*rate),round(seconds[-1]*rate)+1)/rate
    f=np.interp(source_t,seconds,ridge_hz)/divisor
    cycles=np.r_[0,np.cumsum((f[:-1]+f[1:])/(2*rate))]
    count=int(np.floor(cycles[-1]*cycle_samples))
    normalized_cycles=np.arange(count)/cycle_samples
    inverse=np.interp(normalized_cycles,cycles,source_t)
    dense=signal.resample_poly(band,16,1,axis=0,window=('kaiser',8.6),padtype='line')
    position=inverse*rate*16
    y=np.column_stack([np.interp(position,np.arange(len(dense)),dense[:,c]) for c in range(2)])
    metadata=dict(reference_hz=rate/cycle_samples,observed_divisor=divisor,
        meaning='Relative acoustic-cycle candidate, not identified engine order or RPM.',
        source_relative_seconds=[float(seconds[0]),float(seconds[-1])],
        observed_ridge_hz=[float(ridge_hz.min()),float(ridge_hz.max())],
        max_upward_frequency_ratio=float((rate/cycle_samples)/f.min()),
        processing='Stereo retained; offline80-14k FIR, explicit common acoustic-time warp,16x Kaiser interpolation. No normalization/compressor.',
        normalized_frames=len(y))
    return y,metadata
