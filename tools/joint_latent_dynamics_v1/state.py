"""Stable Gaussian matrix dynamics with stationary covariance and continuous interpolation."""
import numpy as np


def prepare(transition):
    a=np.asarray(transition)
    if (a.ndim!=2 or a.shape[0]!=a.shape[1] or not 1<=len(a)<=16
        or np.iscomplexobj(a) or not np.isfinite(a).all()):
        raise ValueError('Finite real square transition with1..16states required')
    a=a.astype(np.float64,copy=True)
    largest=float(np.linalg.svd(a,compute_uv=False)[0])
    if largest>=1:raise ValueError('Unit-covariance innovations require a strict contraction')
    q=np.eye(len(a))-a@a.T
    root=np.linalg.cholesky(q)
    return dict(transition=a,innovation_root=root,maximum_singular_value=largest)


def endpoints(law,noise):
    noise=np.asarray(noise)
    a,root=law['transition'],law['innovation_root']
    if noise.ndim!=2 or noise.shape[1]!=len(a) or not len(noise) or not np.isfinite(noise).all():
        raise ValueError('Finite innovation rows with correct latent dimension required')
    state=np.empty_like(noise,dtype=np.float64);state[0]=noise[0]
    for j in range(1,len(noise)):state[j]=a@state[j-1]+root@noise[j]
    return state


def interpolation_matrix(law,fraction):
    f=float(fraction)
    if not np.isfinite(f) or not 0<=f<=1:raise ValueError('Supported finite interpolation fraction required')
    a=law['transition'];left=1-f
    covariance=(left*left+f*f)*np.eye(len(a))+left*f*(a+a.T)
    value,vector=np.linalg.eigh(covariance)
    if value.min()<=0:raise ValueError('Positive interpolation covariance required')
    whitening=(vector*(1/np.sqrt(value)))@vector.T
    return whitening,covariance


def interpolate(law,left,right,fraction):
    w,_=interpolation_matrix(law,fraction)
    return ((1-fraction)*np.asarray(left)+fraction*np.asarray(right))@w.T


def stationary_lag(law,lag):
    if not isinstance(lag,(int,np.integer)) or lag<0:raise ValueError('Nonnegative integer lag required')
    return np.linalg.matrix_power(law['transition'],int(lag))
