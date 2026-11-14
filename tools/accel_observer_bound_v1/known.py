"""Exact small-observer Wick/lognormal moments; no draws or source data."""
import itertools
from functools import lru_cache
import numpy as np
from .model import bounds


def oracle(gamma,tau,R,tile,size,blocks,fs):
    N=len(tile);n=N*size;length=n*blocks;delta=abs(np.arange(length)[:,None]-np.arange(length)[None,:])
    U=gamma*np.exp(-delta/(fs*tau));C=np.zeros_like(U);valid=delta<len(R);C[valid]=R[delta[valid]]/R[0]
    A=np.eye(N)
    for tag in np.unique(tile):
        kk=np.flatnonzero(tile==tag);A[np.ix_(kk,kk)]-=1/len(kk)
    B=np.kron(np.eye(blocks),np.repeat(np.repeat(A,size,axis=0),size,axis=1)/(N*size**2))/blocks
    BH=B*(1+2*C**2)
    @lru_cache(None)
    def wick(indices):
        if not indices:return 1.
        first=indices[0];rest=indices[1:]
        return sum(C[first,j]*wick(tuple(sorted(rest[:k]+rest[k+1:]))) for k,j in enumerate(rest))
    def logmoment(indices):return np.exp(4*sum(U[i,j] for i,j in itertools.combinations(indices,2)))
    mean=0.;second=0.;fsecond=0.;gradf=0.;gradc=0.
    for a,b in itertools.product(range(length),repeat=2):mean+=B[a,b]*logmoment((a,b))*wick(tuple(sorted((a,a,b,b))))
    for a,b,c,d in itertools.product(range(length),repeat=4):
        g=logmoment((a,b,c,d));fsecond+=BH[a,b]*BH[c,d]*g
        second+=B[a,b]*B[c,d]*g*wick(tuple(sorted((a,a,b,b,c,c,d,d))))
    for i,k,l in itertools.product(range(length),repeat=3):
        g=logmoment((i,i,k,l));gradf+=16*BH[i,k]*BH[i,l]*g
        gradc+=16*B[i,k]*B[i,l]*g*wick(tuple(sorted((i,i,k,k,l,l))))
    vf=fsecond-mean**2;vs=second-mean**2
    return dict(expected=mean,path_variance=vf,carrier_variance=vs-vf,total_variance=vs,
        exact_conditional_gradient=gradf,exact_carrier_normalized_gradient=gradc,
        exact_latent_covariance_norm=float(np.linalg.eigvalsh(U).max()),exact_normalized_carrier_covariance_norm=float(np.linalg.eigvalsh(C).max()))


def known():
    h=np.array([.8,-.3,.2]);R=np.array([np.dot(h[:len(h)-k],h[k:]) for k in range(len(h))])
    fixtures=[(.03,.04,R,np.array([0,0,1]),2,1),(.12,.08,R,np.array([0,0]),1,3),
              (0.,.04,np.array([1.]),np.array([0,0,1]),1,2)]
    output=[];arrays={};maximum_mean=0.
    for index,(gamma,tau,carrier,tile,size,blocks) in enumerate(fixtures):
        value=bounds(gamma,tau,carrier,tile,size,blocks,1,100);exact=oracle(gamma,tau,carrier,tile,size,blocks,100)
        mean_error=abs(value['expected']-exact['expected']);maximum_mean=max(maximum_mean,mean_error);assert mean_error<1e-11
        for name in ['path','carrier','total']:assert exact[name+'_variance']<=value[name+'_variance_bound_run']+1e-11 and exact[name+'_variance']>=-1e-11
        assert exact['exact_conditional_gradient']<=value['conditional_gradient_bound_oneblock']/blocks+1e-11
        assert exact['exact_carrier_normalized_gradient']<=value['carrier_normalized_gradient_bound_oneblock']/blocks+1e-11
        assert exact['exact_latent_covariance_norm']<=value['latent_covariance_norm_bound']+1e-11
        assert exact['exact_normalized_carrier_covariance_norm']<=value['normalized_carrier_covariance_norm_bound']+1e-11
        scaled=bounds(gamma,tau,carrier*7,tile,size,blocks,1,100);reversed_=bounds(gamma,tau,carrier,tile[::-1],size,blocks,1,100)
        for key in value:assert abs(value[key]-scaled[key])<1e-11 and abs(value[key]-reversed_[key])<1e-11
        output.append(dict(gamma=gamma,tau=tau,tile=tile.tolist(),size=size,blocks=blocks,**value,oracle=exact))
        arrays[f'R{index}']=carrier
    assert abs(output[2]['oracle']['path_variance'])<1e-11 and output[2]['path_variance_bound_run']==0
    rejected=0
    for gamma,tile,carrier in [(-.1,np.array([0,0]),R),(.1,np.array([0,1,0]),R),(.1,np.array([0]),np.zeros(2))]:
        try:bounds(gamma,.04,carrier,tile,size=1,blocks=1)
        except ValueError:rejected+=1
    assert rejected==3
    return dict(fixtures=output,maximum_mean_error=maximum_mean,exact_Wick8_and_lognormal4_before_source=True,
        all_variance_and_gradient_bounds_hold=True,zero_gamma=True,signed_carrier=True,white_carrier=True,scaling_and_group_reversal=True,invalid_inputs_rejected=rejected),arrays
