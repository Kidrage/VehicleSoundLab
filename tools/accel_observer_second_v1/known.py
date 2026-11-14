"""Dense full Hessian and four-time expansion, including unequal-size cross-group structure."""
import itertools
import numpy as np
from .model import compile_locals,combine
from accel_observer_bound_v1.known import oracle


def known():
    h=np.array([.8,-.3,.2]);R=np.array([np.dot(h[:len(h)-k],h[k:]) for k in range(len(h))])
    fixtures=[(.03,.04,R,np.array([0,0,1]),2,1),(.12,.08,R,np.array([0,0]),1,3),
        (0.,.04,np.array([1.]),np.array([0,0,1]),1,2),(.06,.05,R,np.array([0,0,1,1,1]),1,2)]
    reports=[];arrays={};maximum=0.
    for index,(gamma,tau,R,tile,size,blocks) in enumerate(fixtures):
        local=compile_locals(gamma,tau,R,tile,size,100);result,group=combine(gamma,tau,tile,local,size,blocks,1,100)
        N=len(tile);length=N*size*blocks;delta=abs(np.arange(length)[:,None]-np.arange(length)[None,:]);rho=np.exp(-delta/(100*tau))
        C=np.zeros_like(rho);ok=delta<len(R);C[ok]=R[delta[ok]]/R[0];A=np.eye(N)
        for tag in np.unique(tile):
            kk=np.flatnonzero(tile==tag);A[np.ix_(kk,kk)]-=1/len(kk)
        B=np.kron(np.eye(blocks),np.repeat(np.repeat(A,size,axis=0),size,axis=1)/(N*size**2))/blocks
        T=B*(1+2*C**2)*np.exp(4*gamma*rho);t=T.sum(axis=1);M=8*(np.diag(t)+T)
        second=float(np.trace((gamma*rho@M)@(gamma*rho@M))/2)
        direct=0.
        for a,b,c,d in itertools.product(range(length),repeat=4):
            direct+=T[a,b]*T[c,d]*(rho[a,c]+rho[a,d]+rho[b,c]+rho[b,d])**2*(4*gamma)**2/2
        expected=dict(term_diagonal=float(t@(rho*rho)@t),term_mixed=float(t@np.diag(rho@T@rho)),term_trace=float(np.trace(T@rho@T@rho)),second_variance_run=second)
        error=max([abs(result[key]-value) for key,value in expected.items()]+[abs(direct-second)])
        maximum=max(maximum,error);assert error<1e-10
        exact=oracle(gamma,tau,R,tile,size,blocks,100)
        assert result['variance_lower_run']<=exact['path_variance']+1e-10 and exact['path_variance']<=result['variance_upper_run']+1e-10
        for m,loc in local.items():
            L=m*size;idx=np.arange(L);C0=np.exp(-abs(idx[:,None]-idx[None,:])/(100*tau))
            T0=loc['kernel'][abs(idx[:,None]-idx[None,:])]*((idx[:,None]//size==idx[None,:]//size)-1/m)
            assert abs(loc['diag_RTR']-np.diag(C0@T0@C0)).max()<1e-10
            assert abs(loc['trace_RTRT']-np.trace(T0@C0@T0@C0))<1e-10
        reports.append(dict(gamma=gamma,tau=tau,tile=tile.tolist(),size=size,blocks=blocks,**result,exact_path_variance=exact['path_variance']))
        arrays[f'R{index}']=R
    assert reports[2]['first_variance_run']==reports[2]['second_variance_run']==reports[2]['remainder_upper_run']==0
    rejected=0
    for gamma,tile in [(-.1,np.array([0,0])),(.1,np.array([0,1,0]))]:
        try:compile_locals(gamma,.04,R,tile,1,100)
        except ValueError:rejected+=1
    assert rejected==2
    return dict(fixtures=reports,maximum_dense_or_four_time_error=maximum,exact_full_second_chaos_before_source=True,
        unequal_group_cross_correlations=True,one_window_zero_group=True,zero_gamma=True,invalid_inputs_rejected=rejected),arrays
