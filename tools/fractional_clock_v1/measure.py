"""Integrated stereo band moments, including inter-harmonic energy."""
import numpy as np
from scipy import signal


def moments(audio, cycle, base, bands, window_cycles):
    size = round(cycle*window_cycles)
    if len(audio)<size:
        raise ValueError('Insufficient retained coordinate for power observations')
    fs = cycle*base
    hz,power = signal.welch(audio,fs=fs,window='hann',nperseg=size,noverlap=size//2,axis=0)
    _,cross = signal.csd(audio[:,0],audio[:,1],fs=fs,window='hann',nperseg=size,noverlap=size//2)
    step = hz[1]-hz[0]
    levels,correlations = [],[]
    for lo,hi in bands:
        keep = (hz>=lo)&(hz<hi)
        p = power[keep].sum(axis=0)*step
        levels.append(p)
        correlations.append(np.conj(cross[keep].sum()*step)/np.sqrt(max(float(p.prod()),1e-60)))
    return np.asarray(levels),np.asarray(correlations)


def compare(first, second):
    a,ac = first
    b,bc = second
    difference = 10*np.log10(np.maximum(b,1e-30)/np.maximum(a,1e-30))
    correlation = abs(bc-ac)
    return dict(power_difference_db_LR=difference.tolist(),complex_correlation_difference=correlation.tolist(),
        maximum_band_power_error_db=float(abs(difference).max()),maximum_complex_correlation_error=float(correlation.max()))


def coherent_moments(audio, cycle, base, bands, window_cycles, denominator):
    """Measure phase-sensitive line capture, rather than only total energy.

    A four-full-period Hann has nulls at every neighbouring fifth-grid line.
    Captured line power changes when an estimated clock smears a known line.
    This remains a measurement convention, not physical noise separation.
    """
    size=round(window_cycles*cycle)
    if len(audio)<size or window_cycles%denominator:
        raise ValueError('Insufficient complete fractional-grid power windows')
    orders=np.arange(1,int(np.floor(max(hi for _,hi in bands)/base*denominator))+1)/denominator
    bins=np.round(orders*window_cycles).astype(int)
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    values=np.array([np.fft.rfft(audio[start:start+size]*window[:,None],axis=0)[bins]*2/window.sum()
        for start in range(0,len(audio)-size+1,size//2)])
    power=np.mean(abs(values)**2,axis=0)/2
    cross=np.mean(values[:,:,0]*np.conj(values[:,:,1]),axis=0)/2
    levels,correlations=[],[]
    for lo,hi in bands:
        keep=(orders*base>=lo)&(orders*base<hi)
        p=power[keep].sum(axis=0)
        levels.append(p)
        correlations.append(cross[keep].sum()/np.sqrt(max(float(p.prod()),1e-60)))
    return np.asarray(levels),np.asarray(correlations)
