"""Optional multi-lag factors; preserve residual RNG, fixed phase and power rule."""
import numpy as np
from .factors import Factors


def render(model,profiles,phase,frames,seed,mask):
    rng=np.random.default_rng(seed);h,k=model['basis'].shape[:2]
    pc=rng.normal(size=k);residual=rng.normal(size=(h,2))
    factors=Factors(profiles,pc,np.random.default_rng(seed^0x589a712d))
    rr=model['residual_rho'];basis=model['basis'];root=model['root']
    covariance=np.array([p['covariance'][0,1] if len(p['coefficients'])>1 else p['coefficients'][0] for p in profiles])

    def coefficients():
        return np.einsum('hkc,k->hc',basis,pc)+np.einsum('hcj,hj->hc',root,residual)

    def advance():
        nonlocal pc,residual
        pc=factors.advance(rng.normal(size=k))
        residual=rr[:,None]*residual+np.sqrt(1-rr*rr)[:,None]*rng.normal(size=(h,2))

    left=coefficients();advance();right=coefficients();output=np.zeros((frames,2))
    for start in range(0,frames,256):
        n=min(256,frames-start);u=np.arange(n)/256
        value=left[None,:,:]+u[:,None,None]*(right-left)[None,:,:]
        variance=np.einsum('hkc,nk->nhc',basis*basis,
            (1-u[:,None])**2+u[:,None]**2+2*u[:,None]*(1-u[:,None])*covariance[None,:])
        residual_variance=np.sum(root*root,axis=2)
        variance+=residual_variance[None,:,:]*((1-u[:,None,None])**2+u[:,None,None]**2+
            2*u[:,None,None]*(1-u[:,None,None])*rr[None,:,None])
        amplitude=model['rms'][None,:,:]*np.exp(value-variance)
        carrier=np.cos(2*np.pi*np.arange(start,start+n)[:,None,None]*np.arange(1,h+1)[None,:,None]/1024+phase[None,:,:])
        output[start:start+n]=np.sum(amplitude*carrier*mask[None,:,None],axis=1)
        left=right;advance();right=coefficients()
    return output
