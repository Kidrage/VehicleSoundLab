"""Linear-overlap fourth cumulants, independent of runtime or source decisions."""
import numpy as np

PAIRS=[(b,c) for b in range(4) for c in range(b,4)]


def correlation(x,y,lags):
    size=1<<(2*len(x)-1).bit_length()
    values=np.fft.irfft(np.conj(np.fft.rfft(x,n=size))*np.fft.rfft(y,n=size),n=size)
    return values[np.asarray(lags)%size]


def curves(x,lags):
    x=np.asarray(x)-np.mean(x,axis=0)
    n=len(x);lags=np.asarray(lags)
    if np.max(abs(lags))>=n:raise ValueError('Positive linear overlap required')
    full=np.mean(x*x,axis=0)
    if np.any(full<=0):raise ValueError('Positive fixed variance required')
    left=np.maximum(-lags,0);right=np.minimum(n-lags,n);count=n-abs(lags)
    prefix=np.vstack((np.zeros(4),np.cumsum(x,axis=0)))
    prefix2=np.vstack((np.zeros(4),np.cumsum(x*x,axis=0)))
    output=[];raw=[];cov=[]
    for b,c in PAIRS:
        a=(prefix[right,b]-prefix[left,b])/count
        d=(prefix[right+lags,c]-prefix[left+lags,c])/count
        m20=(prefix2[right,b]-prefix2[left,b])/count
        m02=(prefix2[right+lags,c]-prefix2[left+lags,c])/count
        m11=correlation(x[:,b],x[:,c],lags)/count
        m21=correlation(x[:,b]**2,x[:,c],lags)/count
        m12=correlation(x[:,b],x[:,c]**2,lags)/count
        m22=correlation(x[:,b]**2,x[:,c]**2,lags)/count
        central=m22-2*d*m21-2*a*m12+4*a*d*m11+d*d*m20+a*a*m02-3*a*a*d*d
        covariance=m11-a*d
        K=central-(m20-a*a)*(m02-d*d)-2*covariance**2
        raw.append(K);output.append(K/full[b]/full[c]);cov.append(covariance/np.sqrt(full[b]*full[c]))
    return dict(cumulant=np.array(raw),normalized=np.array(output),normalized_covariance=np.array(cov),variance=full)


def support(h,rate=48000):
    output=[]
    for b in range(h.shape[0]):
        for i in range(h.shape[1]):
            power=h[b,i]**2;energy=float(power.sum())
            if energy<=0:raise ValueError('Expected nonzero effective response')
            cumulative=np.cumsum(power)/energy
            q=[int(np.searchsorted(cumulative,p)) for p in [.05,.95]]
            output.append(dict(band=b,input=i,energy=energy,centroid_frames=float(np.dot(np.arange(len(power)),power)/energy),
                q05_q95_frames=q,width90_ms=(q[1]-q[0])/rate*1000))
    return output


def summarize(curve,lags):
    lags=np.asarray(lags);mask=(abs(lags)>=384)&(abs(lags)<=960)
    selected=[0,-48,48,-240,240,-480,480,-960,960,-1920,1920]
    return dict(late8_to20ms_mean=np.mean(curve[:,mask],axis=1).tolist(),
        selected={str(lag):curve[:,int(np.flatnonzero(lags==lag)[0])].tolist() for lag in selected})
