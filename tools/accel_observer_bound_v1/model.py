"""Conservative native Gaussian-Poincare bounds for the actual finite energy observer."""
import numpy as np


def rows(kernel,length):
    prefix=np.r_[0.,np.cumsum(kernel[1:length])]
    index=np.arange(length)
    return kernel[0]+prefix[index]+prefix[length-1-index]


def covariance_row_bounds(gamma,tau,R,frames,sample_rate):
    rate=1/(sample_rate*tau);left=(frames-1)//2;right=frames-1-left
    geometric=lambda n: np.exp(-rate)*(-np.expm1(-n*rate))/(-np.expm1(-rate))
    u=gamma*(1+geometric(left)+geometric(right))
    positive=np.abs(R[1:]/R[0]);support=min(len(positive),frames-1)
    if frames>=2*support+1:c=1+2*positive[:support].sum()
    else:
        prefix=np.r_[0.,np.cumsum(positive[:support])];index=np.arange(frames)
        c=np.max(1+prefix[np.minimum(index,support)]+prefix[np.minimum(frames-1-index,support)])
    return float(u),float(c)


def bounds(gamma,tau,covariance,tile,size=480,blocks=8,runs=3,sample_rate=48000):
    R=np.asarray(covariance,dtype=float);tile=np.asarray(tile)
    if R.ndim!=1 or len(R)==0 or not np.all(np.isfinite(R)) or R[0]<=0:raise ValueError('Positive carrier power and finite positive-lag covariance required')
    if not np.isfinite(gamma) or gamma<0 or not np.isfinite(tau) or tau<=0:raise ValueError('Finite nonnegative latent variance and positive time scale required')
    if any(not isinstance(v,(int,np.integer)) or v<1 for v in [size,blocks,runs]) or sample_rate<=0:raise ValueError('Positive integer observer dimensions required')
    if tile.ndim!=1 or len(tile)==0:raise ValueError('Original finite groups required')
    counts=[]
    for tag in np.unique(tile):
        kk=np.flatnonzero(tile==tag)
        if len(kk)>1 and np.any(np.diff(kk)!=1):raise ValueError('Original groups must be contiguous')
        counts.append(len(kk))
    extent=max(counts)*size;rc=np.zeros(extent);rc[:min(extent,len(R))]=R[:extent]/R[0]
    rho=np.exp(-np.arange(extent)/(sample_rate*tau));moment=np.exp(8*gamma+16*gamma*rho)
    H=1+2*rc**2;J=H*moment;C=moment*(3+12*rc**2)
    D=np.expm1(4*gamma*rho)+2*rc**2*np.exp(4*gamma*rho)
    N=len(tile);den=N*size**2;Gu=0.;Gc=0.;mean=0.
    W={key:rows(kernel,size) for key,kernel in [('H',H),('J',J),('C',C),('D',D)]}
    for m in counts:
        if m==1:continue
        total=m*size;coefficient=1-2/m
        absH=(coefficient*np.tile(W['H'],m)+rows(H,total)/m)/den
        weightedH=(coefficient*np.tile(W['J'],m)+rows(J,total)/m)/den
        Gu+=16*np.dot(absH,weightedH)
        absB=2*(1-1/m)/(N*size)
        weightedB=(coefficient*np.tile(W['C'],m)+rows(C,total)/m)/den
        Gc+=16*absB*weightedB.sum()
        mean+=(m*W['D'].sum()-rows(D,total).sum()/m)/den
    Lu,Lc=covariance_row_bounds(gamma,tau,R,N*size*blocks,sample_rate)
    path=Lu*Gu/blocks;carrier=Lc*Gc/blocks
    return dict(expected=float(mean),conditional_gradient_bound_oneblock=float(Gu),carrier_normalized_gradient_bound_oneblock=float(Gc),
        latent_covariance_norm_bound=Lu,normalized_carrier_covariance_norm_bound=Lc,
        path_variance_bound_run=float(path),carrier_variance_bound_run=float(carrier),total_variance_bound_run=float(path+carrier),
        path_variance_bound_pooled=float(path/runs),carrier_variance_bound_pooled=float(carrier/runs),total_variance_bound_pooled=float((path+carrier)/runs))


def tail(bound,difference):
    return 1. if difference==0 else min(1.,float(bound/difference**2))
