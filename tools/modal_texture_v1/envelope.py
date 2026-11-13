"""Fresh positive correlated gains with exact marginal covariance/power control."""
import numpy as np
from sustain_osc_v1.oracle import Gaussian


def states(model,frames,seed):
    factor=np.asarray(model['factor']);dim=len(factor)
    if factor.shape!=(dim,dim) or not np.isfinite(factor).all():raise ValueError('Finite square covariance factor required')
    alpha=model['alpha'];hop=model['hop_frames']
    if not 0<=alpha<1 or not isinstance(frames,int) or frames<1 or hop<1:raise ValueError('Invalid state timing')
    count=(frames-1)//hop+2;rng=Gaussian(seed^0x8CB92BA72F3D8DD7)
    normal=np.fromiter((rng.next() for _ in range(count*dim)),dtype=float).reshape(count,dim)
    out=np.empty_like(normal);out[0]=factor@normal[0]
    for i in range(1,count):out[i]=alpha*out[i-1]+np.sqrt(1-alpha*alpha)*(factor@normal[i])
    return out,normal


def gains(model,state,frames,amount):
    if not np.isfinite(amount) or not 0<=amount<=1:raise ValueError('Amount must be0..1')
    hop=model['hop_frames'];index=np.arange(frames)//hop
    u=.5-.5*np.cos(np.pi*(np.arange(frames)%hop)/hop)
    variance=(1-u)**2+u*u+2*model['alpha']*u*(1-u)
    values=((1-u[:,None])*state[index]+u[:,None]*state[index+1])/np.sqrt(variance[:,None])
    covariance=np.asarray(model['covariance'])
    return np.exp(amount*values-amount*amount*np.diag(covariance)[None,:])
