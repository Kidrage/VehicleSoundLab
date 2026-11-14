"""Joint local projection with replaceable measured acoustic carrier phasors."""
import numpy as np

SELECTED=np.array([1,2,4])


def observe(audio,frequencies,phasors=None,rate=48000,trim=12000):
    frames,hop=9600,960
    if audio.ndim!=2 or audio.shape[1]!=2 or len(audio)<frames+2*trim:
        raise ValueError('Native stereo portion with complete trimmed windows required')
    t=np.arange(len(audio))/rate
    carrier=np.exp(2j*np.pi*t[:,None]*np.asarray(frequencies))
    if phasors is not None:
        if phasors.shape!=(len(audio),3) or abs(abs(phasors)-1).max()>1e-10:
            raise ValueError('Three complete unit acoustic phasors required')
        carrier[:,SELECTED]=phasors
    design=np.column_stack([carrier.real,carrier.imag,np.ones(len(audio))])
    weight=.5-.5*np.cos(2*np.pi*np.arange(frames)/frames)
    starts=np.arange(trim,len(audio)-trim-frames+1,hop)
    coefficient=[];condition=[]
    for first in starts:
        A=design[first:first+frames]
        gram=A.T@(A*weight[:,None])
        eigenvalues=np.linalg.eigvalsh(gram)
        if eigenvalues.min()<=np.finfo(float).eps*gram.shape[0]*eigenvalues.max():
            raise ValueError('Unresolved local joint carrier basis')
        beta=np.linalg.solve(gram,A.T@(audio[first:first+frames,0]*weight))
        m=len(frequencies);coefficient.append(beta[:m]-1j*beta[m:2*m])
        condition.append(float(np.sqrt(eigenvalues.max()/eigenvalues.min())))
    return dict(coefficients=np.array(coefficient),starts=starts,condition=np.array(condition),
                centers=(starts+frames/2)/rate)


def statistics(coefficients,maximum_lag=50):
    magnitude=abs(coefficients[:,SELECTED])
    if np.any(magnitude<=0):raise ValueError('Undefined log magnitude; no source-dependent floor')
    x=np.log(magnitude);mean=x.mean(axis=0);x-=mean
    covariance=x.T@x/len(x)
    curves=np.array([x[:len(x)-lag].T@x[lag:]/(len(x)-lag) for lag in range(maximum_lag+1)])
    return dict(mean_log=mean.tolist(),geometric_mean_amplitude=np.exp(mean).tolist(),
                raw_log_std=np.sqrt(np.diag(covariance)).tolist(),covariance=covariance.tolist(),
                covariance_lags=curves.tolist(),lag_seconds=(np.arange(maximum_lag+1)*.02).tolist(),
                trace_200ms_correlation=float(np.sum(x[:-10]*x[10:])/np.sum(x[:-10]**2)),
                samples=len(x),recorded_trajectory=False),x
