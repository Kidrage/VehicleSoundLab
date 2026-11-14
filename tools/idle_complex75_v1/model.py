"""Generic finite real-vector FIR statistics and covariance-corrected native interpolation."""
import numpy as np
from scipy import signal

KEY=0xC075A4F18E29


def root(matrix,inverse=False):
    e,U=np.linalg.eigh(matrix);limit=np.finfo(float).eps*len(e)*max(float(e.max()),0)
    if e.min() < -max(limit*10,1e-30):raise ValueError('Genuinely indefinite covariance')
    active=e>limit;value=np.zeros_like(e);value[active]=1/np.sqrt(e[active]) if inverse else np.sqrt(e[active])
    return (U*value)@U.T


def covariance(h,maximum=3):
    h=np.asarray(h)
    return np.array([np.einsum('toi,tpi->op',h[:len(h)-lag],h[lag:]) for lag in range(maximum+1)])


def fit(x):
    x=np.asarray(x);assert x.shape==(250,2) and abs(x.mean(axis=0)).max()<1e-12
    w=signal.windows.hann(64,sym=False);sections=np.array([x[j:j+64]*w[:,None] for j in range(0,len(x)-63,32)])
    Z=np.fft.rfft(sections,n=128,axis=1);S=np.einsum('wfi,wfj->fij',Z,Z.conj())/(len(sections)*np.dot(w,w))
    factors=[]
    for s in S:
        e,U=np.linalg.eigh(s);tol=np.finfo(float).eps*len(e)*max(float(e.max()),0)
        if e.min()<-max(tol*10,1e-30):raise ValueError('Invalid empirical spectral Gram')
        factors.append((U*np.sqrt(np.maximum(e,0)))@U.conj().T)
    h=np.roll(np.fft.irfft(factors,n=128,axis=0),64,axis=0)
    target=x.T@x/len(x);T=root(target)@root(covariance(h,0)[0],inverse=True);h=np.einsum('op,tpi->toi',T,h)
    error=float(abs(covariance(h,0)[0]-target).max());assert error<1e-12
    return dict(schema='vsl.idle-complex-log-FIR/1',node_rate=100,taps=h.tolist(),covariance=target.tolist(),
        colour=T.tolist(),spectral_sections=len(sections),covariance_error=error,
        fit_frames=64,fit_hop=32,fit_fft=128,PCM_or_recorded_trajectory=False)


def weights(u):
    return np.column_stack((-.5*u+u*u-.5*u**3,1-2.5*u*u+1.5*u**3,.5*u+2*u*u-1.5*u**3,-.5*u*u+.5*u**3))


def table(model):
    c=covariance(model['taps']);w=weights(np.arange(480)/480);raw=np.zeros((480,2,2))
    for i in range(4):
        for j in range(4):raw+=w[:,i,None,None]*w[:,j,None,None]*(c[j-i] if j>=i else c[i-j].T)
    desired=root(c[0]);T=np.array([desired@root(r,inverse=True) for r in raw]);corrected=np.einsum('fij,fjk,flk->fil',T,raw,T)
    error=float(abs(corrected-c[0]).max());assert error<1e-12
    return dict(weights=w,transform=T,covariance=c[0],raw=raw,error=error)


def nodes(model,seed,seconds):
    h=np.array(model['taps']);warm=len(h)-1;count=int(np.ceil(seconds*100))+5
    white=np.random.Generator(np.random.PCG64(seed^KEY)).standard_normal((count+warm,2));value=np.zeros((count,2))
    for i in range(2):
        for j in range(2):value[:,i]+=signal.oaconvolve(white[:,j],h[:,i,j])[warm:warm+count]
    return value,white


def native(values,compiled,first,count):
    frame=np.arange(first,first+count);k=frame//480;f=frame%480
    raw=sum(compiled['weights'][f,i,None]*values[k+i+1] for i in range(4))
    return np.einsum('fij,fj->fi',compiled['transform'][f],raw)


def gain(x,C):return np.exp(x[:,0]-C[0,0]+1j*(x[:,1]-C[0,1]))
