"""Cubic phase with rate-endpoint coordinates and exact linear profiling."""
import numpy as np
from scipy.linalg import qr,solve_triangular


def geometry(time,duration):
    return np.column_stack((2*np.pi*time,
        .5*np.pi*time**2-np.pi*time**3/(3*duration),
        .5*np.pi*time**2+np.pi*time**3/(3*duration)))


def projection(audio,nominal,weight,time,duration):
    m=len(nominal)
    factors=geometry(time,duration)
    base=2*np.pi*time[:,None]*nominal
    target=weight*audio
    cache={}
    def state(p):
        if 'p' in cache and np.array_equal(p,cache['p']):return cache
        angle=base+factors@np.asarray(p).reshape(3,m)
        cosine,sine=np.cos(angle),np.sin(angle)
        design=np.column_stack((cosine,sine,np.ones(len(time))))
        weighted=weight[:,None]*design
        Q,R=qr(weighted,mode='economic',check_finite=False)
        co=solve_triangular(R,Q.T@target,check_finite=False)
        residual=weighted@co-target
        cache.clear()
        cache.update(p=p.copy(),cosine=cosine,sine=sine,design=design,weighted=weighted,
            Q=Q,R=R,coefficients=co,residual=residual)
        return cache
    def fun(p):return state(p)['residual']
    def jac(p):
        s=state(p)
        co,cosine,sine,Q,R,residual=[s[k] for k in ['coefficients','cosine','sine','Q','R','residual']]
        motion=-sine*co[:m]+cosine*co[m:2*m]
        V=np.column_stack([weight[:,None]*factors[:,j,None]*motion for j in range(3)])
        D=np.zeros((2*m+1,3*m))
        ii=np.arange(m)
        for j in range(3):
            wr=weight*factors[:,j]*residual
            D[ii,j*m+ii]=-(sine*wr[:,None]).sum(axis=0)
            D[m+ii,j*m+ii]=(cosine*wr[:,None]).sum(axis=0)
        return V-Q@(Q.T@V)-Q@solve_triangular(R.T,D,lower=True,check_finite=False)
    return fun,jac,state


def frequency_extent(q,a,duration):
    half=duration/2
    values=[q*(-half)+.5*a*half**2,q*half+.5*a*half**2]
    if a and -half<=-q/a<=half:
        t=-q/a
        values.append(q*t+.5*a*t*t)
    return max(abs(v) for v in values)
