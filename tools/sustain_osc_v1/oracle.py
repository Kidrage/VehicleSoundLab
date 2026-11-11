"""Vectorized independent quadrature sum, not the C harmonic recurrence."""
import math
import numpy as np


class Gaussian:
    def __init__(self,seed):self.state=seed or 1;self.spare=None
    def uniform(self):
        mask=(1<<64)-1;x=self.state
        x^=x>>12;x^=(x<<25)&mask;x^=x>>27;self.state=x&mask
        return (((self.state*2685821657736338717)&mask)>>11)+.5
    def next(self):
        if self.spare is not None:
            x=self.spare;self.spare=None;return x
        radius=math.sqrt(-2*math.log(self.uniform()/2**53))
        angle=2*math.pi*self.uniform()/2**53
        self.spare=radius*math.sin(angle)
        return radius*math.cos(angle)


def render(model,frames=4096,seed=48271):
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
    left=coefficients();advance();right=coefficients();out=[]
    for start in range(0,frames,256):
        n=min(256,frames-start);u=np.arange(n)/256
        value=model['mean'][None,:,:]+left[None,:,:]+u[:,None,None]*(right-left)[None,:,:]
        carrier=np.exp(2j*np.pi*np.arange(start,start+n)[:,None]*np.arange(1,h+1)[None,:]/1024)
        out.append(np.column_stack([np.sum((value[:,:,c]+1j*value[:,:,c+1])*carrier,axis=1).real for c in (0,2)]))
        left=right;advance();right=coefficients()
    return np.concatenate(out)
