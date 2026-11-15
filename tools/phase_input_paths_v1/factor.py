"""Anchored counterfactual phase queries and exact signed waveform differences."""
import numpy as np
from conditional_phase_time_v1.mapping import decode

COUNTERFACTUALS=('base','P_only','U_only','joint')
TERMS=('base','P_change','U_change','interaction')


def phases(product,uniform,knots,cdf,low,high):
    p0=np.ones_like(product);u0=np.full_like(uniform,.5)
    return np.stack([decode(p,u,knots,cdf,low,high) for p,u in (
        (p0,u0),(product,u0),(p0,uniform),(product,uniform))],axis=1)


def wave_terms(counterfactuals):
    b,p,u,j=np.moveaxis(counterfactuals,1,0)
    return np.stack([b,p-b,u-b,j-p-u+b],axis=1)


def signed_budget(matrix):
    mean=matrix.mean(axis=0)
    diagonal=np.diagonal(mean,axis1=-2,axis2=-1).real.reshape(-1,4,2)
    pairs=np.stack([2*mean[:,2*i+np.arange(2),2*j+np.arange(2)].real
        for i in range(4) for j in range(i+1,4)],axis=1)
    shaped=mean.reshape(-1,4,2,4,2)
    total=shaped.sum(axis=(1,3))
    return dict(self_power=diagonal,signed_pairs=pairs,
        total_power=total[:,[0,1],[0,1]].real,complex_LR=total[:,0,1])
