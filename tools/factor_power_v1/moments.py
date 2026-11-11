"""Gaussian log-power expectation and finite-duration variance, no sampling."""
import numpy as np
from numpy.polynomial.legendre import leggauss
from numpy.polynomial.hermite import hermgauss


def autocovariance(profile,lags):
    coefficients=profile['coefficients'];order=len(coefficients)
    r=np.empty(lags+1);r[:min(order,lags+1)]=profile['covariance'][0,:min(order,lags+1)]
    for lag in range(order,lags+1):r[lag]=coefficients@r[lag-order:lag][::-1]
    return r


def interpolate_variance(profiles,nodes):
    r1=np.array([p['covariance'][0,1] if len(p['coefficients'])>1 else p['coefficients'][0] for p in profiles])
    return (1-nodes[:,None])**2+nodes[:,None]**2+2*nodes[:,None]*(1-nodes[:,None])*r1


def expectation(profiles,weights,quadrature_order,hermite_order):
    nodes,w=leggauss(quadrature_order);u=(nodes+1)/2
    variance=interpolate_variance(profiles,u)@(weights*weights).T
    h,hw=hermgauss(hermite_order)
    value=np.exp(2*np.sqrt(2*variance[:,:,None])*h[None,None,:]-2*variance[:,:,None])
    return np.sum(value*hw[None,None,:],axis=2)/np.sqrt(np.pi)


def finite_variance(profiles,weights,steps,quadrature_order):
    # g_n is the integral of normalized squared amplitude within update n.
    # Cov(exp(2z-2v),exp(2w-2q))=exp(4Cov(z,w))-1.
    nodes,w=leggauss(quadrature_order);u=(nodes+1)/2;w=w/2
    base=(1-u[:,None])*(1-u[None,:])+u[:,None]*u[None,:]
    plus=(1-u[:,None])*u[None,:]
    minus=u[:,None]*(1-u[None,:])
    r=np.array([autocovariance(p,steps) for p in profiles])
    covariance=np.zeros((steps,len(weights)))
    for lag in range(steps):
        cross=base[:,:,None]*r[:,lag]+plus[:,:,None]*r[:,lag+1]+minus[:,:,None]*r[:,abs(lag-1)]
        z=np.einsum('uvk,bk->uvb',cross,weights*weights)
        covariance[lag]=np.einsum('u,v,uvb->b',w,w,np.expm1(4*z))
    result=(steps*covariance[0]+2*np.arange(steps-1,0,-1)@covariance[1:])/steps**2
    return result,covariance


def interval_energy(left,right,profiles,weights,order):
    nodes,w=leggauss(order);u=(nodes+1)/2;w=w/2
    variance=interpolate_variance(profiles,u)@(weights*weights).T
    z=((1-u)[None,:,None]*left[:,None,:]+u[None,:,None]*right[:,None,:])@weights.T
    return np.einsum('u,nub->nb',w,np.exp(2*z-2*variance[None,:,:]))
