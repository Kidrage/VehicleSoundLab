"""Forward covariance of filtered iid innovations and the finite energy observer."""
import numpy as np
from scipy import signal


def native_basis(impulse):
    """R_ij(tau)=E[x_i[n]x_j[n+tau]], and coefficient of innovation fourth cumulant."""
    h=np.asarray(impulse);length,channels=h.shape
    second=np.empty((2*length-1,channels,channels));fourth=np.empty_like(second)
    for i in range(channels):
        for j in range(channels):
            second[:,i,j]=signal.correlate(h[:,j],h[:,i],method='fft',mode='full')
            fourth[:,i,j]=signal.correlate(h[:,j]**2,h[:,i]**2,method='fft',mode='full')
    return dict(lags=np.arange(1-length,length),second=second,gaussian=2*second**2,
                fourth=fourth,power=np.sum(h*h,axis=0))


def rectangular_basis(basis,size,maxlag):
    """Covariances of nonoverlapping size-sample mean-square windows, signed lag in windows."""
    weights=np.r_[np.arange(1,size),size,np.arange(size-1,0,-1)]/size**2
    center=-int(basis['lags'][0]);lags=np.arange(-maxlag,maxlag+1)
    result=dict(lags=lags,power=basis['power'])
    for key in ['gaussian','fourth']:
        full=signal.convolve(basis[key],weights[:,None,None],mode='full',method='fft')
        indices=center+size-1+lags*size
        values=np.zeros((len(lags),*basis[key].shape[1:]))
        valid=(indices>=0)&(indices<len(full));values[valid]=full[indices[valid]];result[key]=values
    return result


def within_basis(window,tile,lags):
    """Exact ensemble covariance after local demeaning, not a large-group approximation."""
    tile=np.asarray(tile);counts=np.zeros(len(lags),int);result=dict(lags=np.asarray(lags),power=window['power'])
    for key in ['gaussian','fourth']:
        out=np.zeros((len(lags),*window[key].shape[1:]))
        for tag in np.unique(tile):
            n=int(np.sum(tile==tag));position=np.arange(n);offset=position[None,:]-position[:,None]
            covariance=window[key][offset-int(window['lags'][0])]
            # Independent coordinates may have signed, nonsymmetric lag covariances.
            centered=covariance-covariance.mean(axis=0,keepdims=True)-covariance.mean(axis=1,keepdims=True)+covariance.mean(axis=(0,1),keepdims=True)
            for q,lag in enumerate(lags):
                left=np.arange(max(0,-lag),min(n,n-lag));right=left+lag
                out[q]+=centered[left,right].sum(axis=0)
                if key=='gaussian':counts[q]+=len(left)
        if np.any(counts<=0):raise ValueError('No within-group lag support')
        result[key]=out/counts[:,None,None]
    result['counts']=counts;scale=np.outer(window['power'],window['power'])
    result['normalized_gaussian']=result['gaussian']/scale
    result['normalized_fourth']=result['fourth']/scale
    return result
