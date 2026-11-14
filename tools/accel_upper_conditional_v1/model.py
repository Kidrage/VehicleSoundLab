"""Exact conditional mean of the pre-refilter zero-lag diagonal finite energy statistic."""
import numpy as np
from scipy.fft import next_fast_len


def quadratic_rows(values,positive_kernel):
    """Each row q: q^T K q for even Toeplitz K, including all supported lags."""
    x=np.asarray(values);k=np.asarray(positive_kernel);n=x.shape[1]
    count=min(n,len(k));F=np.fft.rfft(x,n=next_fast_len(2*n-1),axis=1)
    ac=np.fft.irfft(F.conj()*F,n=next_fast_len(2*n-1),axis=1)[:,:count]
    return ac[:,0]*k[0]+2*(ac[:,1:]@k[1:count])


def conditional_mean(gain,carrier_covariance,tile,power,size=480):
    g=np.asarray(gain);R=np.asarray(carrier_covariance);tile=np.asarray(tile);P=np.asarray(power)
    if g.shape!=(len(tile)*size,4) or R.ndim!=2 or R.shape[1]!=4 or P.shape!=(4,) or np.any(P<=0):raise ValueError('Exact four-channel gain history, positive-lag covariance and positive powers required')
    if not np.allclose(R[0],P,rtol=1e-12,atol=0):raise ValueError('Carrier covariance zero lag must equal power')
    q=g*g;windows=q.reshape(len(tile),size,4);mean=windows.mean(axis=1);centered=mean.copy();carrier=np.zeros(4)
    window_quadratic=np.zeros(4);group_correction=np.zeros(4)
    for tag in np.unique(tile):
        indices=np.flatnonzero(tile==tag)
        if len(indices)>1 and np.any(np.diff(indices)!=1):raise ValueError('Original tile groups must be contiguous')
        centered[indices]-=mean[indices].mean(axis=0)
    for i in range(4):
        K=R[:,i]**2/P[i]**2;window_quadratic[i]=quadratic_rows(windows[:,:,i],K).sum()
        for tag in np.unique(tile):
            indices=np.flatnonzero(tile==tag);values=q[indices[0]*size:(indices[-1]+1)*size,i][None]
            group_correction[i]+=quadratic_rows(values,K)[0]/len(indices)
        carrier[i]=2*(window_quadratic[i]-group_correction[i])/(len(tile)*size**2)
    path=np.mean(centered*centered,axis=0)
    return dict(path=path,carrier=carrier,total=path+carrier,window_quadratic=window_quadratic,group_correction=group_correction,
        gain_window_mean=mean)
