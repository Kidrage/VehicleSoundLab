"""Exact native second Gaussian chaos, using finite local blocks and exact OU cross-group ranks."""
import math
import numpy as np
from scipy.signal import lfilter
from accel_observer_projection_v1.model import even_rows,ou_quadratic


def local_operator(h,rate,size,windows,chunk=128):
    length=size*windows;h=np.asarray(h[:length]);r=math.exp(-rate);idx=np.arange(length)
    if windows==1:
        return dict(kernel=h,signed=np.zeros(length),absolute=np.zeros(length),diag_RTR=np.zeros(length),boundary=0.,trace_RTRT=0.)
    group=even_rows(h,length);window=np.tile(even_rows(h,size),windows)
    signed=window-group/windows;absolute=(1-2/windows)*window+group/windows
    RT=np.empty((length,length));v=np.exp(-rate*idx);boundary=[]
    for start in range(0,length,chunk):
        cols=np.arange(start,min(length,start+chunk));offset=abs(idx[:,None]-cols[None,:])
        T=h[offset]*((idx[:,None]//size==cols[None,:]//size)-1/windows)
        boundary.append(float(np.dot(v@T,v[cols])))
        forward=lfilter([1.],[1.,-r],T,axis=0);backward=lfilter([1.],[1.,-r],T[::-1],axis=0)[::-1]
        RT[:,cols]=forward+backward-T
    diagonal=np.empty(length);trace=[]
    for start in range(0,length,chunk):
        rows=np.arange(start,min(length,start+chunk));rho=np.exp(-rate*abs(rows[:,None]-idx[None,:]))
        diagonal[rows]=np.einsum('ij,ij->i',RT[rows],rho)
        trace.append(float(np.einsum('ij,ji->',RT[rows],RT[:,rows])))
    d=math.fsum(boundary);k=math.fsum(trace)
    del RT
    assert abs(diagonal[0]-d)<=1e-9*max(1.,abs(d)) and abs(diagonal[-1]-d)<=1e-9*max(1.,abs(d))
    return dict(kernel=h,signed=signed,absolute=absolute,diag_RTR=diagonal,boundary=d,trace_RTRT=k)


def remainder_cubic(x):
    if x==0:return 0.
    term=x**3/6;total=term
    for degree in range(4,1001):
        term*=x/degree;updated=total+term
        if updated==total:return total
        total=updated
    raise ArithmeticError('Cubic exponential remainder did not converge')


def combine(gamma,tau,tile,locals_,size=480,blocks=8,runs=3,sample_rate=48000):
    entries=sorted([(int(np.flatnonzero(tile==tag)[0]),int(sum(tile==tag))) for tag in np.unique(tile)])
    groups=[m for _,m in entries]*blocks;rate=1/(sample_rate*tau);den=len(tile)*size**2*blocks
    lengths=np.array(groups)*size;d=np.array([locals_[m]['boundary'] for m in groups]);left=np.zeros(len(groups));right=np.zeros(len(groups))
    for g in range(1,len(groups)):left[g]=math.exp(-2*rate)*d[g-1]+math.exp(-2*rate*lengths[g-1])*left[g-1]
    for g in range(len(groups)-2,-1,-1):right[g]=math.exp(-2*rate)*d[g+1]+math.exp(-2*rate*lengths[g+1])*right[g+1]
    terms=[]
    for g,m in enumerate(groups):
        local=locals_[m];rho2=np.exp(-2*rate*np.arange(lengths[g]));D=local['diag_RTR']+left[g]*rho2+right[g]*rho2[::-1]
        terms.append(float(np.dot(local['signed'],D)))
    J=math.fsum(terms)/den**2
    K=(math.fsum(locals_[m]['trace_RTRT'] for m in groups)+2*math.fsum(d*left))/den**2
    t=np.concatenate([locals_[m]['signed'] for m in groups])/den;a=np.concatenate([locals_[m]['absolute'] for m in groups])/den
    A2=ou_quadratic(t,tau/2,sample_rate);Q1=ou_quadratic(t,tau,sample_rate);Qa=ou_quadratic(a,tau,sample_rate)
    first=16*gamma*Q1;second=32*gamma**2*(A2+2*J+K);rem=remainder_cubic(16*gamma)*Qa
    return dict(expected=float(t.sum()),term_diagonal=A2,term_mixed=J,term_trace=K,
        signed_ou_quadratic=Q1,absolute_ou_quadratic=Qa,first_variance_run=first,second_variance_run=second,
        remainder_upper_run=rem,variance_lower_run=first+second,variance_upper_run=first+second+rem,
        first_variance_pooled=first/runs,second_variance_pooled=second/runs,remainder_upper_pooled=rem/runs,
        variance_lower_pooled=(first+second)/runs,variance_upper_pooled=(first+second+rem)/runs,
        exponential_remainder_cubic=remainder_cubic(16*gamma)),dict(groups=np.array(groups),lengths=lengths,left=left,right=right)


def compile_locals(gamma,tau,R,tile,size=480,sample_rate=48000):
    if not np.isfinite(gamma) or gamma<0 or not np.isfinite(tau) or tau<=0:raise ValueError('Nonnegative finite variance and positive time scale required')
    R=np.asarray(R);tile=np.asarray(tile)
    if R.ndim!=1 or len(R)==0 or R[0]<=0 or not np.all(np.isfinite(R)):raise ValueError('Finite covariance with positive power required')
    if tile.ndim!=1 or len(tile)==0 or not isinstance(size,(int,np.integer)) or size<1:raise ValueError('Original groups and integer window size required')
    counts=[]
    for tag in np.unique(tile):
        kk=np.flatnonzero(tile==tag)
        if len(kk)>1 and np.any(np.diff(kk)!=1):raise ValueError('Contiguous groups required')
        counts.append(len(kk))
    rate=1/(sample_rate*tau);length=max(counts)*size;rc=np.zeros(length);rc[:min(length,len(R))]=R[:length]/R[0]
    h=(1+2*rc**2)*np.exp(4*gamma*np.exp(-rate*np.arange(length)))
    return {m:local_operator(h,rate,size,m) for m in sorted(set(counts))}
