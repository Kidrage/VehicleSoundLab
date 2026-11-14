"""Finite, stationary multi-output Gaussian FIR with full native covariance."""
import numpy as np
from scipy import signal

RATE=200
STEP=240


def covariance(taps,maximum=3):
    h=np.asarray(taps)
    return np.array([np.einsum('toi,tpi->op',h[:len(h)-k],h[k:]) for k in range(maximum+1)])


def interpolation(taps):
    c=covariance(taps);u=np.arange(STEP)/STEP
    w=np.column_stack((-.5*u+u*u-.5*u**3,1-2.5*u*u+1.5*u**3,
        .5*u+2*u*u-1.5*u**3,-.5*u*u+.5*u**3))
    raw=np.zeros((STEP,len(c[0]),len(c[0])))
    for i in range(4):
        for j in range(4):raw+=w[:,i,None,None]*w[:,j,None,None]*(c[j-i] if j>=i else c[i-j].T)
    root=np.linalg.cholesky(c[0]);transforms=np.array([np.linalg.solve(np.linalg.cholesky(v).T,root.T).T for v in raw])
    error=float(abs(np.einsum('fij,fjk,flk->fil',transforms,raw,transforms)-c[0]).max())
    assert error<1e-12
    return dict(weights=w,transform=transforms,raw_covariance=raw,covariance=c[0],error=error)


def nodes(taps,seed,seconds):
    h=np.asarray(taps);count=int(np.ceil(seconds*RATE))+5;warm=len(h)-1
    white=np.random.Generator(np.random.PCG64(seed^0x7312FBA84A)).standard_normal((count+warm,h.shape[2]))
    values=np.zeros((count,h.shape[1]))
    for i in range(h.shape[1]):
        for j in range(h.shape[2]):values[:,i]+=signal.oaconvolve(white[:,j],h[:,i,j])[warm:warm+count]
    return values,white


def native(values,table,frames):
    n=np.arange(frames);k=n//STEP;f=n%STEP
    raw=sum(table['weights'][f,i,None]*values[k+i+1] for i in range(4))
    return np.einsum('fij,fj->fi',table['transform'][f],raw)


def known_taps():
    h=np.exp(-.5*((np.arange(64)-31.5)/8)**2);h/=np.linalg.norm(h)
    factor=np.eye(5);factor[1,:2]=[.35,np.sqrt(1-.35**2)]
    return h[:,None,None]*factor[None,:,:]


def delayed_taps():
    h=np.zeros((8,5,5));h[0]=np.diag([.7,.6,.5,.4,.3])
    h[2,1,0]=.2;h[3,2,0]=-.15;h[1,4,3]=.1
    return h
