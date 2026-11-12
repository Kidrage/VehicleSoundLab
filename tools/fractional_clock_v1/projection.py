"""Local joint line estimation, with explicit neighbour and image terms."""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=8)
def kernel(cycle, cycles, orders, offsets, denominator):
    size=round(cycle*cycles)
    time=np.arange(size)/cycle
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    order=np.asarray(orders)
    near=order[:,None]+np.asarray(offsets)[None,:]
    if near.min()<=0:
        raise ValueError('Joint positive line group must stay above DC')
    frequencies=np.concatenate((near,-near),axis=1)
    units=np.round(frequencies*denominator).astype(int)
    difference=units[:,None,:]-units[:,:,None]
    unique=np.unique(difference)
    response=np.exp(2j*np.pi*unique[:,None]/denominator*time[None,:])@window/window.sum()
    gram=response[np.searchsorted(unique,difference)]
    inverse=np.linalg.inv(gram)
    center=int(np.flatnonzero(np.asarray(offsets)==0)[0])
    weights=inverse[:,center,:]
    return weights,near,dict(maximum_gram_condition=float(np.linalg.cond(gram).max()),
        maximum_inverse_row_squared_norm=float(np.max(np.sum(abs(weights)**2,axis=1))),
        neighbour_offsets=list(offsets),negative_images_included=True,
        interpretation='Finite-window least squares separates explicitly modelled neighbours; zero padding only evaluates Fourier integrals, not extra observed time')


def project(audio,cycle,orders,plan,denominator):
    orders=np.asarray(orders,dtype=float)
    size=round(plan['projection_cycles']*cycle)
    padded=round(plan['projection_fft_cycles']*cycle)
    starts=np.arange(0,len(audio)-size+1,round(plan['hop_coarse_cycles']*cycle))
    if len(starts)<3:
        raise ValueError('Insufficient complete joint-projection windows')
    weights,near,meta=kernel(cycle,plan['projection_cycles'],tuple(orders),tuple(plan['neighbour_offsets']),denominator)
    bins=near*plan['projection_fft_cycles']
    if np.max(abs(bins-np.round(bins)))>1e-8:
        raise ValueError('FFT evaluation grid does not contain each modelled neighbour')
    bins=np.round(bins).astype(int)
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    rows=[]
    for start in starts:
        transformed=np.fft.rfft(audio[start:start+size]*window[:,None],n=padded,axis=0)*2/window.sum()
        positive=transformed[bins]
        observed=np.concatenate((positive,np.conj(positive)),axis=1)
        rows.append(np.sum(weights[:,:,None]*observed,axis=1))
    values=np.asarray(rows)*np.exp(-2j*np.pi*starts[:,None,None]*orders[None,:,None]/cycle)
    return starts,values,size,meta


def analytic_check(cycle,plan,denominator):
    time=np.arange(12*cycle)/cycle
    orders=np.array([4.6,4.8,5,5.2,5.4])
    amplitudes=np.array([.12,.23,.7,.17,.09])
    phases=np.array([.7,-.4,.2,1.1,-.8])
    audio=np.column_stack([sum(amp*np.cos(2*np.pi*order*time+phase+channel*.31)
        for order,amp,phase in zip(orders,amplitudes,phases)) for channel in (0,1)])
    _,values,_,meta=project(audio,cycle,[5.],plan,denominator)
    truth=amplitudes[2]*np.exp(1j*(phases[2]+np.array([0,.31])))
    error=float(np.max(abs(values[:,0]-truth)))
    if error>1e-10:
        raise ValueError('Joint projection fails independent known neighbour coefficients')
    return dict(maximum_known_complex_coefficient_error=error,**meta)
