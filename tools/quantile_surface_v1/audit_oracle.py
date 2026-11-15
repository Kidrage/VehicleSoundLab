"""Independent bisection row inverses and Gauss moments; no renderer imports."""
import numpy as np


def row_inverse(uniform,row_index,cdf,low,high):
    left=np.zeros(len(uniform),int);right=np.full(len(uniform),len(low)-1,int)
    while np.any(left<right):
        active=left<right
        middle=(left+right)//2
        take_left=uniform<cdf[row_index,middle+1]
        right=np.where(active & take_left,middle,right);left=np.where(active & ~take_left,middle+1,left)
    start=cdf[row_index,left];mass=cdf[row_index,left+1]-start
    return low[left]+(uniform-start)/mass*(high[left]-low[left])


def phase(product,uniform,knots,cdf,low,high):
    at=np.clip(np.searchsorted(knots,product,side='left')-1,0,len(knots)-2)
    w=np.clip((product-knots[at])/(knots[at+1]-knots[at]),0.,1.)
    a=row_inverse(uniform,at,cdf,low,high);b=row_inverse(uniform,at+1,cdf,low,high)
    return (1-w)*a+w*b


def midpoint_moments(cdf,low,high):
    # Independent Gauss integration. np.interp uses the exact inverse graph
    # (CDF, phase edges), avoiding the production row_inverse implementation.
    assert np.array_equal(low[1:],high[:-1])
    x,w=np.polynomial.legendre.leggauss(16);phase_edges=np.r_[low[0],high]
    cell_angles=(low[:,None]+high[:,None])/2+(high-low)[:,None]*x/2
    cell_integral=(np.exp(1j*cell_angles)*w).sum(axis=1)/2
    old=[];new=[]
    for i in range(len(cdf)-1):
        original=((np.diff(cdf[i])+np.diff(cdf[i+1]))/2)@cell_integral
        edges=np.unique(np.r_[cdf[i],cdf[i+1]]);width=np.diff(edges)
        u=(edges[:-1,None]+edges[1:,None])/2+width[:,None]*x/2
        a=np.interp(u.ravel(),cdf[i],phase_edges).reshape(u.shape)
        b=np.interp(u.ravel(),cdf[i+1],phase_edges).reshape(u.shape)
        candidate=np.sum(width[:,None]*w[None,:]*np.exp(.5j*(a+b)))/2
        old.append(original);new.append(candidate)
    return np.asarray(old),np.asarray(new)


def generate(bundle,amplitude,common,uniform,root,edges,bands,name):
    n=np.arange(len(amplitude));h=amplitude.shape[1];orders=np.arange(1,h+1)
    group=np.zeros((len(n),len(edges)-1,2));power=np.zeros((len(n),2*len(bands)));cross=np.zeros((len(n),len(bands)),complex)
    maximum=[];rms=[]
    for j in range(h):
        raw=bundle[name][j];cdf=raw.copy();cdf[:,0]=0.;cdf[:,-1]=1.
        product=amplitude[:,j,0]*amplitude[:,j,1]/bundle['mean_product'][j]
        delta=phase(product,uniform[:,j],bundle['knots'][j],cdf,bundle['low'][j],bundle['high'][j])
        maximum.append(abs(np.diff(delta)).max());rms.append(np.sqrt(np.mean(np.diff(delta)**2)))
        hz=(j+1)*root;at=int(np.searchsorted(edges,hz,side='right')-1)
        v=min(max((hz-19200)/2400,0.),1.);taper=1-3*v*v+2*v*v*v
        amp=amplitude[:,j]*taper;carrier=2*np.pi*(n%1024)/1024*(j+1)
        group[:,at,0]+=amp[:,0]*np.cos(carrier+common[:,j]+delta/2)
        group[:,at,1]+=amp[:,1]*np.cos(carrier+common[:,j]-delta/2)
        for b,(lo,hi) in enumerate(bands):
            if lo<=hz<hi:
                power[:,2*b]+=amp[:,0]**2/2;power[:,2*b+1]+=amp[:,1]**2/2
                cross[:,b]+=amp[:,0]*amp[:,1]*(np.cos(delta)+1j*np.sin(delta))/2
    return group,np.asarray(maximum),np.asarray(rms),power,cross
