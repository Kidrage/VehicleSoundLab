"""Dense native first-chaos coefficients and exact four-time observer variances before sources."""
import numpy as np
from .model import coefficients,project
from accel_observer_bound_v1.known import oracle


def known():
    h=np.array([.8,-.3,.2]);R=np.array([np.dot(h[:len(h)-k],h[k:]) for k in range(len(h))])
    fixtures=[(.03,.04,R,np.array([0,0,1]),2,1),(.12,.08,R,np.array([0,0]),1,3),(0.,.04,np.array([1.]),np.array([0,0,1]),1,2)]
    result=[];arrays={};maximum=0.
    for index,(gamma,tau,R,tile,size,blocks) in enumerate(fixtures):
        signed,absolute=coefficients(gamma,tau,R,tile,size,100);value=project(gamma,tau,signed,absolute,blocks,1,100)
        N=len(tile);n=N*size;total=n*blocks;delta=abs(np.arange(total)[:,None]-np.arange(total)[None,:]);rho=np.exp(-delta/(100*tau))
        C=np.zeros_like(rho);valid=delta<len(R);C[valid]=R[delta[valid]]/R[0];A=np.eye(N)
        for tag in np.unique(tile):
            ii=np.flatnonzero(tile==tag);A[np.ix_(ii,ii)]-=1/len(ii)
        B=np.kron(np.eye(blocks),np.repeat(np.repeat(A,size,axis=0),size,axis=1)/(N*size**2))/blocks
        T=B*(1+2*C**2)*np.exp(4*gamma*rho);t=T.sum(axis=1);a=abs(T).sum(axis=1)
        first=float(16*gamma*t@rho@t);qabs=float(a@rho@a)
        error=max(abs(np.tile(signed,blocks)/blocks-t).max(),abs(np.tile(absolute,blocks)/blocks-a).max(),abs(value['first_variance_run']-first),abs(value['absolute_ou_quadratic_run']-qabs))
        maximum=max(maximum,float(error));assert error<1e-11
        exact=oracle(gamma,tau,R,tile,size,blocks,100)
        assert abs(value['expected']-exact['expected'])<1e-11
        assert first<=exact['path_variance']+1e-11 and exact['path_variance']<=value['variance_upper_run']+1e-11
        scaled=project(gamma,tau,*coefficients(gamma,tau,R*7,tile,size,100),blocks,1,100)
        reverse=project(gamma,tau,*coefficients(gamma,tau,R,tile[::-1],size,100),blocks,1,100)
        for key in value:assert abs(value[key]-scaled[key])<1e-11 and abs(value[key]-reverse[key])<1e-11
        result.append(dict(gamma=gamma,tau=tau,tile=tile.tolist(),size=size,blocks=blocks,**value,exact_path_variance=exact['path_variance']))
        arrays[f'R{index}']=R;arrays[f't{index}']=signed;arrays[f'a{index}']=absolute
    assert result[2]['first_variance_run']==result[2]['remainder_variance_upper_run']==0
    rejected=0
    for gamma,tile in [(-.1,np.array([0,0])),(.1,np.array([0,1,0]))]:
        try:coefficients(gamma,.04,R,tile,1,100)
        except ValueError:rejected+=1
    assert rejected==2
    return dict(fixtures=result,maximum_dense_error=maximum,exact_four_time_variance_brackets_before_source=True,
        continuous_block_correlation=True,signed_finite_carrier=True,zero_gamma=True,scale_and_reversal=True,invalid_inputs_rejected=rejected),arrays
