"""FFT local products and explicit cross-group pairs, independent of production recurrences."""
import math
import numpy as np
from scipy.linalg import matmul_toeplitz
from scipy.signal import lfilter
from numpy.polynomial.legendre import leggauss


def product(h,rate):
    """Exact finite Toeplitz product via FFT boundaries and its displacement identity."""
    n=len(h);rho=np.exp(-rate*np.arange(n));U=np.empty((n,n))
    U[0]=matmul_toeplitz((h,h),rho,check_finite=False,workers=2)
    U[:,0]=matmul_toeplitz((rho,rho),h,check_finite=False,workers=2)
    # Shift the finite convolution sum; only its two endpoint terms change.
    for i in range(n-1):U[i+1,1:]=U[i,:-1]+rho[i+1]*h[1:]-rho[n-1-i]*h[:0:-1]
    return U


def product_controls():
    from scipy.linalg import toeplitz
    errors=[]
    for n in [1,2,7,129,481]:
        for rate in [.0001,.03,1.2]:
            h=np.cos(np.arange(n)*.21)*np.exp(-np.arange(n)*.005);rho=np.exp(-rate*np.arange(n))
            expected=matmul_toeplitz((rho,rho),toeplitz(h),check_finite=False,workers=2)
            actual=product(h,rate);error=float(abs(actual-expected).max()/max(1.,abs(expected).max()))
            errors.append(error);assert error<1e-10
    return dict(cases=len(errors),maximum_full_matrix_relative_error=max(errors),gate=1e-10)


def local(gamma,tau,R,size,m,fs):
    n=size*m;idx=np.arange(n);rate=1/(fs*tau);rho=np.exp(-rate*idx)
    rc=np.zeros(n);rc[:min(n,len(R))]=R[:n]/R[0]
    kernel=(1+2*rc*rc)*np.exp(4*gamma*rho)
    RT=product(kernel,rate);RT/=-m;small=product(kernel[:size],rate)
    edge=matmul_toeplitz((kernel[:size],kernel[:size]),rho[:size],check_finite=False,workers=2)
    for b in range(m):
        lo=b*size;hi=lo+size
        RT[lo:hi,lo:hi]+=small
        RT[:lo,lo:hi]+=np.exp(-rate*(lo-np.arange(lo)))[:,None]*edge
        RT[hi:,lo:hi]+=np.exp(-rate*(np.arange(hi,n)-(hi-1)))[:,None]*edge[::-1]
    signed=np.zeros(n);absolute=np.zeros(n);boundary=0.
    for first in range(0,n,128):
        cols=np.arange(first,min(first+128,n))
        T=kernel[abs(idx[:,None]-cols)]*((idx[:,None]//size==cols//size)-1/m)
        signed+=T.sum(axis=1);absolute+=abs(T).sum(axis=1)
        boundary+=float(rho@T@rho[cols])
    diagonal=np.empty(n);trace=0.
    for first in range(0,n,128):
        rows=np.arange(first,min(first+128,n))
        diagonal[rows]=np.einsum('ij,ij->i',RT[rows],np.exp(-rate*abs(rows[:,None]-idx)))
        trace+=float(np.einsum('ij,ji->',RT[rows],RT[:,rows]))
    return dict(kernel=kernel,signed=signed,absolute=absolute,diag_RTR=diagonal,boundary=boundary,trace_RTRT=trace)


def quadratic(x,rate):
    filtered=lfilter([1.],[1.,-math.exp(-rate)],x)
    return float(2*np.dot(x,filtered)-np.dot(x,x))


def combined(gamma,tau,tile,ls,size=480,blocks=8,runs=3,fs=48000):
    changes=np.r_[0,np.flatnonzero(np.diff(tile)!=0)+1,len(tile)]
    groups=np.tile(np.diff(changes),blocks);lengths=groups*size
    starts=np.r_[0,np.cumsum(lengths)[:-1]];ends=starts+lengths-1;rate=1/(fs*tau)
    d=np.array([ls[m]['boundary'] for m in groups]);left=np.zeros(len(groups));right=left.copy()
    for g in range(len(groups)):
        left[g]=np.dot(d[:g],np.exp(-2*rate*(starts[g]-ends[:g])))
        right[g]=np.dot(d[g+1:],np.exp(-2*rate*(starts[g+1:]-ends[g])))
    den=len(tile)*size**2*blocks;J=0.;K=sum(ls[m]['trace_RTRT'] for m in groups)
    for g,m in enumerate(groups):
        rho2=np.exp(-2*rate*np.arange(lengths[g]));loc=ls[m]
        J+=float(loc['signed']@(loc['diag_RTR']+left[g]*rho2+right[g]*rho2[::-1]))
        K+=2*d[g]*left[g]
    J/=den**2;K/=den**2
    t=np.concatenate([ls[m]['signed'] for m in groups])/den
    a=np.concatenate([ls[m]['absolute'] for m in groups])/den
    A2=quadratic(t,2*rate);Q1=quadratic(t,rate);Qa=quadratic(a,rate)
    z,w=leggauss(48);z=(z+1)/2;w=w/2;x=16*gamma
    remainder=x**3/2*np.dot(w,(1-z)**2*np.exp(x*z))
    first=16*gamma*Q1;second=32*gamma**2*(A2+2*J+K);rem=remainder*Qa
    values=dict(expected=float(t.sum()),term_diagonal=A2,term_mixed=J,term_trace=K,
        signed_ou_quadratic=Q1,absolute_ou_quadratic=Qa,first_variance_run=first,second_variance_run=second,
        remainder_upper_run=rem,variance_lower_run=first+second,variance_upper_run=first+second+rem,
        first_variance_pooled=first/runs,second_variance_pooled=second/runs,remainder_upper_pooled=rem/runs,
        variance_lower_pooled=(first+second)/runs,variance_upper_pooled=(first+second+rem)/runs,
        exponential_remainder_cubic=remainder)
    return values,dict(groups=groups,lengths=lengths,left=left,right=right)


def known_followup():
    # No original recording, source fit or archived source coefficient is read here.
    from .model import compile_locals,combine
    R=np.array([1.,-.3,.15]);tile=np.array([0,0,1,2,2,2]);gamma=.07;tau=.04;fs=100;size=2;blocks=2
    locs=compile_locals(gamma,tau,R,tile,size,fs)
    base,_=combine(gamma,tau,tile,locs,size,blocks,1,fs)
    scaled,_=combine(gamma,tau,tile,compile_locals(gamma,tau,9*R,tile,size,fs),size,blocks,1,fs)
    reverse,_=combine(gamma,tau,tile[::-1],compile_locals(gamma,tau,R,tile[::-1],size,fs),size,blocks,1,fs)
    fft={m:local(gamma,tau,R,size,m,fs) for m in locs}
    independent,_=combined(gamma,tau,tile,fft,size,blocks,1,fs)
    n=len(tile)*size*blocks;ids=np.tile(np.repeat(tile,size),blocks)+np.repeat(np.arange(blocks)*3,len(tile)*size)
    delta=abs(np.arange(n)[:,None]-np.arange(n));rho=np.exp(-delta/(fs*tau))
    rc=np.zeros_like(rho);ok=delta<len(R);rc[ok]=R[delta[ok]]/R[0]
    B=np.eye(len(tile))
    for tag in np.unique(tile):
        ii=np.flatnonzero(tile==tag);B[np.ix_(ii,ii)]-=1/len(ii)
    B=np.kron(np.eye(blocks),np.repeat(np.repeat(B,size,axis=0),size,axis=1))/(len(tile)*size**2*blocks)
    T=B*(1+2*rc*rc)*np.exp(4*gamma*rho);t=T.sum(axis=1);M=8*(np.diag(t)+T)
    dense=float(np.trace((gamma*rho@M)@(gamma*rho@M))/2)
    errors={name:max(abs(base[k]-other[k]) for k in base) for name,other in [('amplitude_scale',scaled),('reversal',reverse),('independent_fft',independent)]}
    errors['dense_hessian']=abs(dense-base['second_variance_run'])
    assert max(errors.values())<1e-10,errors
    return dict(passed=True,errors=errors,finite_Toeplitz_product=product_controls(),scaling_means_normalized_carrier_covariance_invariance=True,
        timing='After producer source reads, BEFORE independent audit source reads; not a retroactive producer control.')
