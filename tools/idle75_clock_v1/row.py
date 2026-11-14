"""Generic stationary FIR-row clock with exact marginal interpolation variance."""
import numpy as np
from scipy import signal

KEY=0x619A2EF5B37C


def prepare(taps,rate):
    h=np.asarray(taps);assert h.ndim==2 and len(h)>3
    c=np.array([np.sum(h[:len(h)-k]*h[k:]) for k in range(4)])
    C=np.array([[c[abs(i-j)] for j in range(4)] for i in range(4)])
    return dict(taps=h,node_rate=rate,covariance=C,variance=c[0])


def nodes(model,seed,seconds):
    h=model['taps'];warm=len(h)-1;count=int(np.ceil(seconds*model['node_rate']))+5
    white=np.random.Generator(np.random.PCG64(seed^KEY)).standard_normal((count+warm,h.shape[1]))
    value=sum(signal.oaconvolve(white[:,i],h[:,i])[warm:warm+count] for i in range(h.shape[1]))
    return value,white


def weights(u):
    u=np.asarray(u)
    w=np.column_stack((-.5*u+u*u-.5*u**3,1-2.5*u*u+1.5*u**3,.5*u+2*u*u-1.5*u**3,-.5*u*u+.5*u**3))
    dw=np.column_stack((-.5+2*u-1.5*u*u,-5*u+4.5*u*u,.5+4*u-4.5*u*u,-u+1.5*u*u))
    return w,dw


def native(model,values,frames,clock,first=0):
    q=np.arange(first,first+frames)/48000*model['node_rate'];position=q*clock
    k=np.floor(position).astype(int);u=position-k
    if k.max()+4>=len(values):raise ValueError('Insufficient complete procedural nodes')
    w,dw=weights(u);slab=values[k[:,None]+np.arange(1,5)]
    raw=np.sum(w*slab,axis=1);draw=np.sum(dw*slab,axis=1)
    variance=np.einsum('ti,ij,tj->t',w,model['covariance'],w)
    dv=2*np.einsum('ti,ij,tj->t',dw,model['covariance'],w)
    if variance.min()<=0:raise ValueError('Nonpositive interpolated variance')
    normalization=np.sqrt(model['variance']/variance)
    x=raw*normalization
    derivative=(draw-.5*raw*dv/variance)*normalization*q
    return x,derivative


def gain(model,values,frames,parameters,first=0):
    clock,strength=parameters;x,dx=native(model,values,frames,clock,first)
    g=np.exp(strength*x-strength*strength*model['variance'])
    jac=np.column_stack((g*strength*dx,g*(x-2*strength*model['variance'])))
    return g,jac,x
