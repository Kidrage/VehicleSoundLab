"""Native FFT local maxima feed the unchanged bounded frequency-moment solver."""
import numpy as np
from .center import centered


def cells(nominal):
    order=np.argsort(nominal)
    boundaries=[20.,*[(nominal[a]+nominal[b])/2 for a,b in zip(order[:-1],order[1:])],250.]
    result=np.empty((len(nominal),2))
    for i,label in enumerate(order):result[label]=boundaries[i:i+2]
    return result


def native_peaks(audio,rate,nominal):
    assert len(audio)==rate and audio.shape[1]==2
    bounds=cells(nominal)
    w=np.sin(np.pi*np.arange(rate)/rate)**2
    power=abs(np.fft.rfft(w[:,None]*audio,axis=0))**2
    chosen=np.full((len(nominal),2),-1,dtype=int)
    candidate_sets=[]
    for line,(lo,hi) in enumerate(bounds):
        channels=[]
        for ch in range(2):
            allowed=[k for k in range(max(1,int(np.ceil(lo))),min(len(power)-1,int(np.ceil(hi))))
                     if power[k,ch]>power[k-1,ch] and power[k,ch]>power[k+1,ch]]
            ranked=sorted(allowed,key=lambda k:power[k,ch],reverse=True)
            if ranked:chosen[line,ch]=ranked[0]
            channels.append([dict(native_bin_Hz=k,power=float(power[k,ch])) for k in ranked])
        candidate_sets.append(channels)
    shape=chosen.shape
    result=dict(moment=np.zeros(shape,dtype=complex),derivative_moment=np.zeros(shape,dtype=complex),
        amplitude=np.zeros(shape),relative_db=np.full(shape,-300.),supported=np.zeros(shape,dtype=bool),
        frequency_Hz=np.full(shape,np.nan),initial_frequency_Hz=np.full(shape,np.nan),
        root_resolved=np.zeros(shape,dtype=bool),root_residual_Hz=np.full(shape,np.nan),
        endpoint_offsets_Hz=np.full((*shape,2),np.nan),root_iterations=np.zeros(shape,dtype=int))
    for ch in range(2):
        present=chosen[:,ch]>=0
        if present.any():
            values=centered(np.column_stack((audio[:,ch],audio[:,ch])),rate,chosen[present,ch])
            for key,value in values.items():result[key][present,ch]=value[:,0]
    result.update(selected_native_bin_Hz=chosen,peak_present=chosen>=0,cell_bounds_Hz=bounds,candidates=candidate_sets)
    return result
