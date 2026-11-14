"""Signed first Gaussian projection and positive analytic remainder bound of F=E[S|g]."""
import numpy as np
from scipy.fft import next_fast_len


def even_rows(kernel,count):
    prefix=np.r_[0.,np.cumsum(kernel[1:count])];index=np.arange(count)
    return kernel[0]+prefix[index]+prefix[count-1-index]


def coefficients(gamma,tau,R,tile,size=480,sample_rate=48000):
    R=np.asarray(R,dtype=float);tile=np.asarray(tile)
    if not np.isfinite(gamma) or gamma<0 or not np.isfinite(tau) or tau<=0 or not np.isfinite(sample_rate) or sample_rate<=0:raise ValueError('Finite nonnegative variance and positive time scales required')
    if R.ndim!=1 or len(R)==0 or not np.all(np.isfinite(R)) or R[0]<=0:raise ValueError('Carrier covariance with positive power required')
    if tile.ndim!=1 or len(tile)==0 or not isinstance(size,(int,np.integer)) or size<1:raise ValueError('Original groups and integer native window size required')
    counts=[]
    for tag in np.unique(tile):
        indices=np.flatnonzero(tile==tag)
        if len(indices)>1 and np.any(np.diff(indices)!=1):raise ValueError('Contiguous original groups required')
        counts.append((indices,len(indices)))
    extent=max(m for _,m in counts)*size;rc=np.zeros(extent);rc[:min(extent,len(R))]=R[:extent]/R[0]
    rho=np.exp(-np.arange(extent)/(sample_rate*tau));kernel=(1+2*rc**2)*np.exp(4*gamma*rho)
    local=even_rows(kernel,size);N=len(tile);signed=np.zeros(N*size);absolute=np.zeros(N*size)
    for indices,m in counts:
        if m==1:continue
        group=even_rows(kernel,m*size);window=np.tile(local,m);where=slice(indices[0]*size,(indices[-1]+1)*size)
        signed[where]=(window-group/m)/(N*size**2)
        absolute[where]=((1-2/m)*window+group/m)/(N*size**2)
    return signed,absolute


def ou_quadratic(values,tau,sample_rate):
    n=len(values);length=next_fast_len(2*n-1);F=np.fft.rfft(values,n=length)
    ac=np.fft.irfft(F.conj()*F,n=length)[:n]
    return float(ac[0]+2*np.dot(ac[1:],np.exp(-np.arange(1,n)/(sample_rate*tau))))


def linear_remainder(x):
    if x==0:return 0.
    term=x*x/2;total=term
    for degree in range(3,1001):
        term*=x/degree;updated=total+term
        if updated==total:return total
        total=updated
    raise ArithmeticError('Exponential remainder did not converge')


def project(gamma,tau,signed,absolute,blocks=8,runs=3,sample_rate=48000):
    if any(not isinstance(v,(int,np.integer)) or v<1 for v in [blocks,runs]):raise ValueError('Positive integer continuous blocks and independent runs required')
    signed=np.asarray(signed);absolute=np.asarray(absolute)
    if signed.ndim!=1 or signed.shape!=absolute.shape or len(signed)==0:raise ValueError('Matched native coefficient rows required')
    qs=ou_quadratic(np.tile(signed,blocks)/blocks,tau,sample_rate)
    qa=ou_quadratic(np.tile(absolute,blocks)/blocks,tau,sample_rate)
    first=16*gamma*qs;remainder=linear_remainder(16*gamma)*qa
    return dict(expected=float(signed.sum()),signed_ou_quadratic_run=qs,absolute_ou_quadratic_run=qa,
        exponential_remainder=linear_remainder(16*gamma),first_variance_run=float(first),remainder_variance_upper_run=float(remainder),
        variance_upper_run=float(first+remainder),first_variance_pooled=float(first/runs),
        remainder_variance_upper_pooled=float(remainder/runs),variance_upper_pooled=float((first+remainder)/runs))
