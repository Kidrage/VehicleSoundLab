"""Gaussian FIR-row covariance and positive-gain moments at arbitrary real times."""
import numpy as np
from idle75_clock_v1.row import weights


def node_covariance(taps):
    h=np.asarray(taps)
    return np.array([np.sum(h[:len(h)-k]*h[k:]) for k in range(len(h))])


def features(model,times,clock):
    q=np.asarray(times)*model['node_rate'];p=q*clock;k=np.floor(p).astype(int)
    w,dw=weights(p-k);C=np.array(model['covariance']);V=model['variance']
    variance=np.einsum('ti,ij,tj->t',w,C,w)
    derivative=2*np.einsum('ti,ij,tj->t',dw,C,w)*q
    scale=np.sqrt(V/variance);ds=-.5*scale*derivative/variance
    return k,w*scale[:,None],dw*(scale*q)[:,None]+w*ds[:,None]


def covariance(model,times,clock):
    k,w,dw=features(model,times,clock);c=node_covariance(model['taps']);n=len(k)
    value=np.zeros((n,n));derivative=np.zeros((n,n));pad=np.r_[c,0.]
    for first in range(0,n,256):
        end=min(first+256,n);delta=k[first:end,None]-k[None,:]
        for i in range(4):
            for j in range(4):
                indices=np.minimum(abs(delta+i-j),len(c));lag=pad[indices]
                value[first:end]+=(w[first:end,i,None]*w[None,:,j])*lag
                derivative[first:end]+=(dw[first:end,i,None]*w[None,:,j]+w[first:end,i,None]*dw[None,:,j])*lag
    assert abs(value.diagonal()-model['variance']).max()<1e-12
    return value,derivative


def gain_covariance(model,times,parameters):
    clock,strength=parameters;C,D=covariance(model,times,clock);V=model['variance']
    exponential=np.exp(strength**2*(C-V))
    result=np.exp(-strength**2*V)*np.expm1(strength**2*C)
    D*=strength**2;D*=exponential
    C*=2*strength;C*=exponential
    C-=2*strength*V*result
    mean=float(np.exp(-.5*strength**2*V));mean_derivative=-strength*V*mean
    return result,D,C,mean,mean_derivative
