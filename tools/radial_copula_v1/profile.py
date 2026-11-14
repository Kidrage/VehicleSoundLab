"""Generic joint radial/circular copula compiler; no engine or waveform timeline."""
import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata
from .quantiles import integral


def compile_rows(rows, components=12, rho_cap=.95):
    n = len(rows)
    h = rows.shape[1]//4
    q = rows.reshape(n,h,2,2)
    z = q[...,0]+1j*q[...,1]
    amplitude = abs(z).reshape(n,2*h)
    fixed = np.angle(z.mean(axis=0))
    phase = np.angle(z).reshape(n,2*h)
    unwrapped = np.empty_like(phase)
    gap = np.empty(2*h)
    for j in range(2*h):
        order = np.sort(phase[:,j])
        gaps = np.diff(np.r_[order,order[0]+2*np.pi])
        at = int(np.argmax(gaps))
        cut = order[at]+gaps[at]/2
        unwrapped[:,j] = cut+np.mod(phase[:,j]-cut,2*np.pi)
        gap[j] = gaps[at]
    amp_table = np.sort(amplitude,axis=0)
    target = np.mean(amplitude**2,axis=0)
    normalization = np.sqrt(np.divide(target,integral(amp_table,2),out=np.ones_like(target),where=target>0))
    amp_table *= normalization
    phase_table = np.sort(unwrapped,axis=0)
    features = np.column_stack([amplitude,unwrapped])
    tolerance = np.r_[64*np.finfo(float).eps*np.maximum(amplitude.max(axis=0),1e-6),np.full(2*h,1e-12)]
    active = np.ptp(features,axis=0)>tolerance
    scores = ndtri((rankdata(features,axis=0,method='average')-.5)/n)
    scores -= scores.mean(axis=0)
    std = np.sqrt(np.mean(scores**2,axis=0))
    scores = np.divide(scores,std,out=np.zeros_like(scores),where=active & (std>0))
    u,s,v = np.linalg.svd(scores,full_matrices=False)
    rank = int(np.sum(s>max(float(s[0])*1e-10,1e-12))) if len(s) else 0
    k = min(components,rank,n-1)
    basis = (v[:k]*(s[:k,None]/np.sqrt(n))).T
    pc = u[:,:k]*np.sqrt(n)
    # Canonical signs make the stored model less dependent on SVD conventions.
    for j in range(k):
        if basis[np.argmax(abs(basis[:,j])),j]<0:
            basis[:,j] *= -1;pc[:,j] *= -1
    residual = scores-pc@basis.T
    residual_std = np.sqrt(np.mean(residual**2,axis=0))
    def rho(values):
        denominator = np.sum(values[:-1]**2,axis=0)
        return np.clip(np.divide(np.sum(values[1:]*values[:-1],axis=0),denominator,
                                 out=np.zeros(values.shape[1]),where=denominator>1e-20),-rho_cap,rho_cap)
    result = dict(amplitude=amp_table,phase=phase_table,fixed_phase=fixed,basis=basis,rho=rho(pc),
                  residual_std=residual_std,residual_rho=rho(residual),active=active,
                  target_amplitude_second=target,source_amplitude_fourth=np.mean(amplitude**4,axis=0),
                  maximum_empty_phase_gap=gap)
    return result,dict(scores=scores,pc=pc,residual=residual,amplitude=amplitude,phase_unwrapped=unwrapped,
                       source_rows=rows,normalization=normalization)
