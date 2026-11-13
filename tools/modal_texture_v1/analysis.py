"""Joint native-window magnitudes; no frequency/phase trajectory export."""
import numpy as np


def observe(audio,frequencies,plan):
    n=plan['observation_frames'];hop=plan['observation_hop'];rate=plan['sample_rate']
    frequencies=np.asarray(frequencies,dtype=float)
    if audio.ndim!=2 or audio.shape[1]!=2 or len(audio)<n or not np.isfinite(audio).all():raise ValueError('Finite stereo training samples required')
    if not len(frequencies) or not np.isfinite(frequencies).all() or np.any(frequencies<=0) or np.any(frequencies>=rate/2):raise ValueError('Finite independent frequencies required')
    time=(np.arange(n)-n/2)/rate;angle=2*np.pi*time[:,None]*frequencies
    design=np.column_stack((np.cos(angle),np.sin(angle),np.ones(n)))
    w=np.sin(np.pi*np.arange(n)/n)
    # Fixed design factorization; exact joint projection avoids treating ordinary beating as AM.
    weighted=design*w[:,None];u,s,vh=np.linalg.svd(weighted,full_matrices=False)
    if s[-1]<=s[0]*np.finfo(float).eps*max(weighted.shape):raise ValueError('Unresolved modal design')
    operator=(vh.T/s)@u.T;operator*=w[None,:]
    starts=np.arange(0,len(audio)-n+1,hop)
    coefficients=np.stack([operator@audio[start:start+n,0] for start in starts])
    m=len(frequencies);complex_value=coefficients[:,:m]-1j*coefficients[:,m:2*m]
    return dict(coefficients=complex_value,DC=coefficients[:,-1],
        starts=starts,centers_seconds=(starts+n/2)/rate,condition_number=float(s[0]/s[-1]),
        singular_values=s,design=design,operator=operator)


def compile_statistics(observed,plan):
    magnitude=abs(observed['coefficients']);floor=np.maximum(magnitude.mean(axis=0)*plan['magnitude_floor_fraction'],1e-30)
    values=np.log(np.maximum(magnitude,floor));values-=values.mean(axis=0)
    covariance=values.T@values/len(values)
    std=np.sqrt(np.maximum(np.diag(covariance),0.));scale=np.minimum(1.,plan['maximum_log_amplitude_std']/np.maximum(std,1e-30))
    limited=values*scale;covariance=limited.T@limited/len(values)
    lag=plan['correlation_lag'];denominator=float(np.sum(limited[:-lag]**2))
    raw=float(np.sum(limited[:-lag]*limited[lag:])/denominator) if denominator>1e-24 else 0.
    alpha=max(0.,min(plan['correlation_ceiling'],raw))
    eigenvalues,eigenvectors=np.linalg.eigh(covariance)
    if eigenvalues.min() < -1e-12:raise ValueError('Non-PSD amplitude covariance')
    factor=eigenvectors*np.sqrt(np.maximum(eigenvalues,0.))[None,:]
    model=dict(schema='vsl.modal-amplitude-statistics/1',covariance=covariance.tolist(),factor=factor.tolist(),
        alpha=alpha,hop_frames=plan['generator_hop'],recorded_trajectory=False,
        scope='Windowed independent-modal magnitude proxy; not physical combustion or phase coherence')
    evidence=dict(observation_windows=len(values),raw_log_std=std.tolist(),row_scales=scale.tolist(),
        limited_log_std=np.sqrt(np.diag(covariance)).tolist(),raw_alpha=raw,alpha=alpha,
        correlation_lag_frames=lag*plan['observation_hop'],observation_window_frames=plan['observation_frames'],
        phase_used_for_generation=False,floor_magnitude=floor.tolist())
    return model,evidence,values
