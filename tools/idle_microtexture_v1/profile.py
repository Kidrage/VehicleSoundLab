"""Train-only excess short-time amplitude statistics, without trajectory export."""
import numpy as np


def statistics(power):
    if power.ndim!=2 or len(power)<3 or not np.isfinite(power).all() or np.any(power<=0):
        raise ValueError('Positive finite band energies required')
    v=.5*np.log(power);v-=v.mean(axis=0)
    return v.T@v/len(v),v[:-1].T@v[1:]/(len(v)-1)


def compile_model(source,controls,hop):
    cov,lag=statistics(source);pairs=[statistics(x) for x in controls]
    excess=cov-np.mean([x[0] for x in pairs],axis=0)
    eigen,vectors=np.linalg.eigh(excess)
    if eigen.min()<=0:raise ValueError('Excess covariance is not positive definite; no projection or ridge permitted')
    excess_lag=lag-np.mean([x[1] for x in pairs],axis=0)
    raw=float(np.trace(excess_lag)/np.trace(excess));alpha=max(0.,min(.98,raw))
    model=dict(covariance=excess.tolist(),factor=(vectors*np.sqrt(eigen)[None,:]).tolist(),alpha=alpha,hop_frames=hop)
    evidence=dict(source_covariance=cov.tolist(),phase_control_covariance=np.mean([x[0] for x in pairs],axis=0).tolist(),
        excess_lag1=excess_lag.tolist(),excess_eigenvalues=eigen.tolist(),raw_alpha=raw,
        windows=len(source),log_amplitude_std=np.sqrt(np.diag(excess)).tolist(),physical_modulation_identified=False)
    return model,evidence
