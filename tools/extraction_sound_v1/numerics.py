"""Engineering floating-point sensitivity, not a certified FFT-error bound.

No energy floor: uncertainty scales with the actual input. Raw powers/statistics
remain untouched, including positive leakage and genuine signals below1e-24.
"""
import numpy as np


def sensitivity(spectrum,frames,weights,groups,power,cross):
    n=frames.shape[1]
    count=32*n
    eps=np.finfo(np.float64).eps
    gamma=count*eps/(1-count*eps)
    error=gamma*np.sum(abs(frames),axis=1)
    powers=[];crosses=[]
    for b in range(6):
        weighted_error=error*np.sqrt(np.sum(weights[groups==b]))
        root=np.sqrt(power[:,b])
        powers.append(2*root*weighted_error+weighted_error**2)
        crosses.append(root[:,0]*weighted_error[:,1]+root[:,1]*weighted_error[:,0]
            +weighted_error[:,0]*weighted_error[:,1])
    uncertainty=np.stack(powers,axis=1)
    cross_uncertainty=np.stack(crosses,axis=1)
    mean=power.mean(axis=0);mean_error=uncertainty.mean(axis=0)
    defined=mean>0
    relative=np.zeros_like(mean)
    np.divide(mean_error,mean,out=relative,where=defined)
    resolved=mean>mean_error
    return dict(power_uncertainty=uncertainty,cross_uncertainty=cross_uncertainty,
        mean_power_uncertainty=mean_error,power_lower_margin=mean-mean_error,
        power_relative_uncertainty=relative,power_resolution_defined=defined,
        power_resolved=resolved,coherence_resolved=resolved.all(axis=1),
        FFT_absolute_sensitivity=error,roundoff_gamma=np.array(gamma),
        sensitivity_is_certified_bound=np.array(False))
