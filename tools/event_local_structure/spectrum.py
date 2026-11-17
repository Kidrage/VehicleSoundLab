"""Native finite Hann transforms, channel powers and power-crossing widths."""
import numpy as np
from scipy.signal import find_peaks

RATE=48000
WINDOWS=(768,1536,3072,6144)
EDGES=((60,300),(300,1200),(1200,4500),(4500,14000))


def observe(audio,frames,hop):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():
        raise ValueError('Finite native stereo recording required')
    if type(frames) is not int or frames not in WINDOWS or type(hop) is not int or not 1<=hop<=frames or len(x)<frames:
        raise ValueError('Supported finite native window and hop required')
    starts=np.arange(0,len(x)-frames+1,hop)
    window=.5-.5*np.cos(2*np.pi*np.arange(frames)/frames)
    offsets=starts[:,None]+np.arange(frames)
    transform=np.fft.rfft(x[offsets]*window[None,:,None],axis=1)
    scale=np.full(frames//2+1,2/(frames*float(window@window)))
    scale[[0,-1]]*=.5
    power=abs(transform)**2*scale[None,:,None]
    hz=np.fft.rfftfreq(frames,1/RATE)
    # FFT phase is referred to window start; move to the exact periodic-Hann centre.
    centre=transform*np.where(np.arange(len(hz))%2, -1., 1.)[None,:,None]*(2/window.sum())
    return dict(starts=starts,centres=(starts+frames/2)/RATE,hz=hz,power=power,
        complex_center=centre,window_frames=frames,hop_frames=hop)


def half_width(power,index,df):
    target=power[index]*.5
    left=index
    while left>0 and power[left]>target:left-=1
    right=index
    while right<len(power)-1 and power[right]>target:right+=1
    if left==0 or right==len(power)-1:return None
    lo=left+(target-power[left])/(power[left+1]-power[left])
    hi=right-1+(target-power[right-1])/(power[right]-power[right-1])
    return float((hi-lo)*df)


def inventories(observed):
    mean=observed['power'].mean(axis=-1)
    hz=observed['hz'];df=hz[1]-hz[0]
    band=(hz>=60)&(hz<14000)
    maximum=float(mean[:,band].max(initial=0))
    rows=[]
    for j,power in enumerate(mean):
        logged=10*np.log10(np.maximum(power,1e-300))
        indices,props=find_peaks(logged,prominence=6.,distance=2)
        local=float(power[band].max(initial=0))
        keep=band[indices]&(power[indices]>=local*10**(-36/10))&(power[indices]>=maximum*1e-6)
        peaks=[]
        for index,prominence in zip(indices[keep],props['prominences'][keep]):
            den=logged[index-1]-2*logged[index]+logged[index+1]
            delta=np.clip(.5*(logged[index-1]-logged[index+1])/den,-.5,.5) if den else 0.
            frequency=float((index+delta)*df)
            coefficient=observed['complex_center'][j,index]
            peaks.append(dict(bin=int(index),hz=frequency,power_LR=observed['power'][j,index].tolist(),
                prominence_db=float(prominence),half_power_width_hz=half_width(power,index,df),
                coefficient_real_LR=coefficient.real.tolist(),coefficient_imag_LR=coefficient.imag.tolist(),
                phase_summary_eligible=bool(frequency*observed['window_frames']/RATE>=3),
                LR_relative_phase_cycles=float(np.angle(coefficient[1]*coefficient[0].conjugate())/(2*np.pi))))
        rows.append(dict(frame=j,first_sample=int(observed['starts'][j]),
            centre_seconds=float(observed['centres'][j]),peaks=peaks))
    return rows
