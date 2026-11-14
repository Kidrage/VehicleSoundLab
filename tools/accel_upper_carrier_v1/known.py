"""Known matrix phase, finite covariance/filter and exact detrended-Welch controls."""
import numpy as np
from .spectral import RATE,factor,covariance,density,apply_gain,refilter


def psd(h,size):
    H=np.fft.rfft(h,n=size,axis=0);C=np.einsum('fiq,fjq->fij',H.conj(),H)
    one=np.full(size//2+1,2.);one[[0,-1]]=1
    return C*one[:,None,None]/RATE


def known():
    h=np.zeros((16,4,4));h[0]=np.diag([1.,.8,.3,.2]);h[3,1,0]=-.4;h[2,2,0]=.2;h[5,3,1]=.3
    h[1,0,2]=.1;h[7,2,3]=-.12;size=256;C=psd(h,size);compiled,meta=factor(C,size)
    error=float(abs(psd(compiled,size)-C).max()/abs(C).max());assert error<1e-12 and np.max(abs(C[:,0,1].imag))>1e-6
    rank=h[:,:,:1];rank_C=psd(rank,size);rank_h,_=factor(rank_C,size);rank_error=float(abs(psd(rank_h,size)-rank_C).max()/abs(rank_C).max());assert rank_error<1e-12
    zero,_=factor(np.zeros_like(C),size);assert not zero.any()
    scaled,_=factor(C*1e-18,size);scaled_error=float(abs(psd(scaled,size)-C*1e-18).max()/(abs(C).max()*1e-18));assert scaled_error<1e-12
    lags,R=covariance(h,2048);zero_gain=apply_gain(lags,R,np.zeros((4,4)),.023);assert np.array_equal(zero_gain,R)
    independent=np.eye(4)*.04;Ri=apply_gain(lags,R,independent,.023)
    assert abs(R[18,0,1])>.1 and abs(Ri[18,0,1]-R[18,0,1]*np.exp(-.04))<1e-12
    identical=np.repeat(h[:,:1],4,axis=1);ll,RR=covariance(identical,2048);common=apply_gain(ll,RR,np.full((4,4),.04),.023)
    assert abs(common-common[:,0,0,None,None]).max()<1e-12
    q=np.array([[1,.7,.8,1.1],[.1,-.2,.05,.1],[-.03,.04,-.1,0.]])
    lo,ref=refilter(lags,R,q,2048);direct=np.zeros((len(h)+len(q)-1,4,4))
    for i in range(4):
        for j in range(4):direct[:,i,j]=np.convolve(h[:,i,j],q[:,i])
    direct_lags,direct_R=covariance(direct,2048);assert np.array_equal(lo,direct_lags)
    refilter_error=float(abs(ref-direct_R).max());assert refilter_error<1e-12
    N=32;win=.5-.5*np.cos(2*np.pi*np.arange(N)/N);expected=density(lags,R,N,N);scalar=np.zeros_like(expected)
    for k in range(N//2+1):
        a=win*np.exp(-2j*np.pi*k*np.arange(N)/N);a-=a.mean()
        for u in range(N):
            for v in range(N):
                lag=v-u
                if abs(lag)<16:scalar[k]+=a[u].conj()*a[v]*R[lag+15]
        scalar[k]*=(1 if k in [0,N//2] else 2)/(RATE*np.dot(win,win))
    welch_error=float(abs(expected-scalar).max());assert welch_error<1e-12
    return dict(matrix_factor_relative_error=error,rank_one_relative_error=rank_error,scaled1e18_relative_error=scaled_error,
        zero_factor_exact=True,complex_CSD_phase_checked=True,zero_gain_exact=True,common_gain_identical_carriers=True,
        independent_gain_cross_attenuation=True,short_refilter_error=refilter_error,detrended_Welch_error=welch_error),dict(
        impulse=h,target=C,compiled=compiled,rank_target=rank_C,rank_compiled=rank_h,scaled=scaled,lags=lags,covariance=R,
        independent_covariance=Ri,q=q,refilter_lags=lo,refilter_covariance=ref,Welch=expected,explicit_Welch=scalar)
