"""Radial soft-L1 on stacked real/imaginary complex residuals."""
import numpy as np


def pairs(values):
    assert len(values)%2==0
    half=len(values)//2
    return np.stack((values[:half],values[half:]),axis=1)


def stacked(values):return np.concatenate((values[:,0],values[:,1]),axis=0)


def geometry(residual,scale):
    r=pairs(residual);norm=np.linalg.norm(r,axis=1)
    v=1/np.sqrt(1+(norm/scale)**2)
    direction=np.divide(r,norm[:,None],out=np.zeros_like(r),where=norm[:,None]>0)
    return r,v,direction


def cost(residual,scale):
    r=pairs(residual);power=np.sum(r*r,axis=1)
    return float(np.sum(power/(np.sqrt(1+power/scale**2)+1)))


def gradient(residual,scale):
    r,v,_=geometry(residual,scale)
    return stacked(r*v[:,None])


def hessian_apply(residual,values,scale,power=1.):
    """Exact symmetric H^power, with positive radial/tangential eigenvalues."""
    _,v,direction=geometry(residual,scale);x=pairs(values)
    vector=values.ndim==1
    if vector:x=x[:,:,None]
    unit=direction[:,:,None];along=np.sum(x*unit,axis=1,keepdims=True)
    y=v[:,None,None]**power*x+(v[:,None,None]**(3*power)-v[:,None,None]**power)*unit*along
    return stacked(y[:,:,0] if vector else y)


def quadratic(residual,matrix,scale):
    psi=gradient(residual,scale)
    weighted=hessian_apply(residual,matrix,scale,.5)
    return weighted.T@weighted,matrix.T@psi,weighted,-hessian_apply(residual,psi,scale,-.5)
