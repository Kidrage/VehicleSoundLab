"""Exact real-Gaussian white null for the original overlapping harmonic observer."""
import numpy as np


def covariance(orders, rows, cycle_samples=1024, cycles=4, hop=256):
    size=cycle_samples*cycles; window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    orders=np.asarray(orders,dtype=int);frequency=orders*cycles
    values=[]
    for lag in range(rows):
        shift=lag*hop
        if shift>=size:
            values.append(0.)
            continue
        product=np.zeros(size)
        product[shift:]=window[shift:]*window[:size-shift]
        transform=np.fft.fft(product)
        R=transform[(frequency[:,None]-frequency[None,:])%size]
        P=transform[(frequency[:,None]+frequency[None,:])%size]
        # Q=.5*sum|Z|^2; Z=2/window.sum * harmonic projection.
        values.append(np.sum(abs(R)**2+abs(P)**2)*4/window.sum()**4)
    lag=np.array(values)
    population=lag/lag[0]
    matrix=lag[abs(np.arange(rows)[:,None]-np.arange(rows)[None,:])]
    centered=matrix-matrix.mean(axis=0)[None,:]-matrix.mean(axis=1)[:,None]+matrix.mean()
    variance=np.trace(centered)/rows
    finite=np.array([np.diag(centered,k).mean()/variance for k in range(rows)])
    return dict(covariance_lags=lag,population_correlation=population,
                finite_demeaned_correlation=finite,finite_centered_covariance=centered)


def observed(power, maximum=8):
    centered=power-power.mean(axis=0)
    variance=np.mean(centered**2,axis=0)
    return np.array([np.mean(centered[:-k]*centered[k:],axis=0)/variance
                     for k in range(1,maximum+1)])
