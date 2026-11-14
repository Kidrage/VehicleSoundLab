"""Exact finite innovations, known before source comparison."""
import itertools
import numpy as np
from numpy.polynomial.hermite import hermgauss
from .kernel import native_basis,rectangular_basis,within_basis


def enumerate_pair(h,lag,p):
    node,w=hermgauss(5);node=np.r_[0,node*np.sqrt(2/p)];w=np.r_[1-p,w*p/np.sqrt(np.pi)]
    times=sorted(set([-k for k in range(len(h))]+[lag-k for k in range(len(h))]))
    index=np.array(list(itertools.product(range(len(node)),repeat=len(times))))
    values=node[index];weights=np.prod(w[index],axis=1)
    x=sum(h[k,0]*values[:,times.index(-k)] for k in range(len(h)))
    y=sum(h[k,1]*values[:,times.index(lag-k)] for k in range(len(h)))
    return np.sum(weights*x*y),np.sum(weights*x*x*y*y)-np.sum(weights*x*x)*np.sum(weights*y*y)


def known():
    h=np.array([[1.,-.3],[.2,.8]]);basis=native_basis(h);maximum=0.;saved={};stats=[]
    for p in [1.,.2]:
        kappa=3/p-3;rows=[]
        for lag in range(-3,4):
            second,squared=enumerate_pair(h,lag,p)
            if abs(lag)<len(h):q=lag+len(h)-1;expect=basis['second'][q,0,1];sq=basis['gaussian'][q,0,1]+kappa*basis['fourth'][q,0,1]
            else:expect=sq=0.
            maximum=max(maximum,abs(second-expect),abs(squared-sq));rows.append([lag,second,squared])
        saved[f'enumerated_p{p}']=np.array(rows);stats.append(dict(p=p,kappa=kappa))
    assert maximum<1e-12
    node,w=hermgauss(5);node=np.r_[0,node*np.sqrt(10)];w=np.r_[.8,w*.2/np.sqrt(np.pi)]
    independent=np.array(list(itertools.product(range(6),repeat=4)));v=node[independent];weights=np.prod(w[independent],axis=1)
    x=v[:,:2]@h[:,0];y=v[:,2:]@h[:,1]
    independent_error=max(abs(np.sum(weights*x*y)),abs(np.sum(weights*x*x*y*y)-np.sum(weights*x*x)*np.sum(weights*y*y)))
    assert independent_error<1e-12 and basis['second'][1,0,1]<0
    tile=np.repeat([0,1,2],[3,7,6]);lags=np.arange(-2,3);window=rectangular_basis(basis,3,8);observed=within_basis(window,tile,lags)
    # Assemble every sample pair and every centering coefficient independently.
    error=0.;n=len(tile);center=np.eye(n)
    for tag in np.unique(tile):
        idx=np.flatnonzero(tile==tag);center[np.ix_(idx,idx)]-=1/len(idx)
    direct={}
    for key in ['gaussian','fourth']:
        raw=np.zeros((n,n,2,2))
        for u in range(n):
            for v in range(n):
                for left in range(3):
                    for right in range(3):
                        lag=(v-u)*3+right-left
                        if abs(lag)<len(h):raw[u,v]+=basis[key][lag+len(h)-1]/9
        centered=np.einsum('ab,bcij,dc->adij',center,raw,center)
        out=[]
        for lag in lags:
            pairs=[(u,u+lag) for u in range(n) if 0<=u+lag<n and tile[u]==tile[u+lag]]
            out.append(sum(centered[u,v] for u,v in pairs)/len(pairs))
        out=np.array(out);error=max(error,float(abs(out-observed[key]).max()));direct[key]=out
    assert error<1e-12 and np.any(observed['fourth'][:,0,1]<0)
    for key in ['gaussian','fourth']:assert abs(observed[key]-observed[key][::-1].transpose(0,2,1)).max()<1e-12
    scaled=within_basis(rectangular_basis(native_basis(h*.173),3,8),tile,lags)
    swapped=within_basis(rectangular_basis(native_basis(h[:,::-1]),3,8),tile,lags)
    for key in ['normalized_gaussian','normalized_fourth']:
        assert abs(scaled[key]-observed[key]).max()<1e-12
        assert abs(swapped[key]-observed[key][:,::-1,::-1]).max()<1e-12
    saved.update(impulse=h,tile=tile,window_lags=window['lags'],window_gaussian=window['gaussian'],window_fourth=window['fourth'],
                 within_lags=lags,within_gaussian=observed['gaussian'],within_fourth=observed['fourth'],counts=observed['counts'])
    return dict(enumerated_second_fourth_error=maximum,finite_observer_error=error,independent_stream_cross_error=float(independent_error),mixtures=stats,
                signed_negative_centered_lags=True,gain_permutation_reversal=True,independent_stream_cross_zero=True),saved
