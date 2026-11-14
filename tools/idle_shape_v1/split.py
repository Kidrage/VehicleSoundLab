"""Complementary continuous resonant shapes driven by one existing source."""
import numpy as np
from scipy import signal


def coefficients(crossover,rate=48000):
    k=np.tan(np.pi*crossover/rate)
    return np.array([k/(1+k),k/(1+k)]),np.array([1.,(k-1)/(k+1)])


def split(x,crossover):
    b,a=coefficients(crossover);low=signal.lfilter(b,a,x)
    return low,np.asarray(x)-low


def response(kernel,crossover):
    h=np.r_[np.asarray(kernel['taps']),np.zeros(1024)]
    lo,hi=split(h,crossover);gram=np.array([[lo@lo,lo@hi],[hi@lo,hi@hi]])
    total=float(h@h);eigen=np.linalg.eigvalsh(gram)
    tail=float((lo[-512:]@lo[-512:]+hi[-512:]@hi[-512:])/total)
    if eigen.min()<=0 or tail>=1e-24:raise ValueError('Unqualified complementary response covariance')
    return dict(crossover_hz=crossover,gram=gram.tolist(),variance=total,
        minimum_eigenvalue=float(eigen.min()),tail_power_fraction=tail),np.stack((lo,hi))


def factors(delta,amount,gram,total):
    exponent=amount*np.asarray(delta)/4
    if np.max(abs(exponent))>200:raise ValueError('Unrepresentable shape factors; no clipping')
    lo=np.exp(exponent);hi=np.exp(-exponent);g=np.asarray(gram)
    variance=g[0,0]*lo*lo+2*g[0,1]*lo*hi+g[1,1]*hi*hi
    if np.any(variance<=0) or not np.isfinite(variance).all():raise ValueError('Invalid shape variance')
    normal=np.sqrt(variance/total)
    return lo/normal,hi/normal


def shape(original,low,high,delta,amount,model):
    if amount==0:return original.copy()
    a,b=factors(delta,amount,model['gram'],model['variance'])
    return a*low+b*high


def known():
    frequency=np.linspace(0,np.pi,1001)
    transfer_error=cross_error=0.
    for crossover in [1700.,3100.,6000.,11000.]:
        b,a=coefficients(crossover);_,lo=signal.freqz(b,a,worN=frequency);hi=1-lo
        transfer_error=max(transfer_error,float(abs(lo+hi-1).max()))
        cross_error=max(cross_error,float(abs((lo*hi.conj()).real).max()))
    assert transfer_error<1e-14 and cross_error<1e-14
    # Exact ensemble with genuinely nonzero branch cross covariance.
    u=np.array([[-1.,-1.],[-1.,1.],[1.,-1.],[1.,1.]])
    y=u@np.array([[.8,.3],[.2,-.4]]);gram=y.T@y/4;total=float(np.mean(y.sum(axis=1)**2))
    assert abs(gram[0,1])>.01
    error=0.
    for amount in [0.,.5,1.]:
        for delta in [-1.3,0.,.8]:
            a,b=factors(np.array([delta]),amount,gram,total)
            actual=np.mean((a*y[:,0]+b*y[:,1])**2)
            error=max(error,abs(float(actual-total)))
    assert error<1e-14
    b,a=coefficients(1700);x=np.sin(np.arange(1000)*.31);lo,hi=split(x,1700)
    assert abs(lo+hi-x).max()<1e-15
    zero=shape(x,lo,hi,np.ones(len(x)),0.,dict(gram=gram.tolist(),variance=total))
    assert np.array_equal(zero,x)
    return dict(complementary_transfer_error=transfer_error,stationary_cross_power_real_error=cross_error,
        nonzero_cross_covariance_ensemble_variance_error=error,zero_amount_exact=True)
