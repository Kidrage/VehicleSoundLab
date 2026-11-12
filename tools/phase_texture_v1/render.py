"""Fixed accepted amplitudes with one common, bounded HF phase displacement."""
import numpy as np
from sustain_osc_v1.oracle import Gaussian


def render(model,frames,seed,delay,mask):
    h,k=model['basis'].shape[:2];rng=Gaussian(seed)
    pc=np.array([rng.next() for _ in range(k)])
    residual=np.array([rng.next() for _ in range(h*4)]).reshape(h,4)
    def coefficients():
        return np.einsum('hkc,k->hc',model['basis'],pc*np.sqrt(3/(2+model['rho'])))+np.einsum(
            'hcj,hj->hc',model['root'],residual*np.sqrt(3/(2+model['residual_rho']))[:,None])
    def advance():
        nonlocal pc,residual
        pc=model['rho']*pc+np.sqrt(1-model['rho']**2)*np.array([rng.next() for _ in range(k)])
        r=model['residual_rho'][:,None]
        residual=r*residual+np.sqrt(1-r*r)*np.array([rng.next() for _ in range(h*4)]).reshape(h,4)
    left=coefficients();advance();right=coefficients()
    out=np.zeros((frames,2));delta=np.zeros_like(out)
    fixed=np.arctan2(model['mean'][:,1::2],model['mean'][:,0::2])
    hz=np.arange(1,h+1)*46.875
    for start in range(0,frames,256):
        n=min(256,frames-start);u=np.arange(n)/256
        value=model['mean'][None,:,:]+left[None,:,:]+u[:,None,None]*(right-left)[None,:,:]
        amplitude=np.hypot(value[:,:,0::2],value[:,:,1::2])
        phase=2*np.pi*np.arange(start,start+n)[:,None,None]*hz[None,:,None]/48000+fixed[None,:,:]
        original=np.cos(phase)
        changed=np.cos(phase+2*np.pi*delay[start:start+n,None,None]*hz[None,:,None])
        out[start:start+n]=(amplitude*original).sum(axis=1)
        delta[start:start+n]=(amplitude*(changed-original)*mask[None,:,None]).sum(axis=1)
        left=right;advance();right=coefficients()
    return out,delta
