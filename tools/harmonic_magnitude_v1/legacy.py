"""Independent direct sum of the accepted C phase-fixed recipe for subtraction."""
import numpy as np
from sustain_osc_v1.oracle import Gaussian


def parse(path):
    lines = path.read_text(encoding='ascii').splitlines()
    header = lines[0].split()
    assert header[:6]==['VSL_SUSTAIN_OSC','1','48000','1024','256',header[5]]
    h,k = map(int,header[5:7]);assert h==300 and k==12
    rows = np.array([[float(v) for v in line.split()] for line in lines[2:]])
    assert rows.shape==(h,4+4*k+1+16)
    return dict(mean=rows[:,:4],basis=rows[:,4:4+4*k].reshape(h,k,4),
        rho=np.array([float(v) for v in lines[1].split()]),residual_rho=rows[:,4+4*k],
        root=rows[:,-16:].reshape(h,4,4))


def render(model,frames,seed,mask):
    h,k = model['basis'].shape[:2];rng = Gaussian(seed)
    pc = np.array([rng.next() for _ in range(k)])
    residual = np.array([rng.next() for _ in range(h*4)]).reshape(h,4)

    def coefficients():
        return np.einsum('hkc,k->hc',model['basis'],pc*np.sqrt(3/(2+model['rho'])))+np.einsum(
            'hcj,hj->hc',model['root'],residual*np.sqrt(3/(2+model['residual_rho']))[:,None])

    def advance():
        nonlocal pc,residual
        pc = model['rho']*pc+np.sqrt(1-model['rho']**2)*np.array([rng.next() for _ in range(k)])
        r = model['residual_rho'][:,None]
        residual = r*residual+np.sqrt(1-r*r)*np.array([rng.next() for _ in range(h*4)]).reshape(h,4)

    left=coefficients();advance();right=coefficients()
    output,high = np.zeros((frames,2)),np.zeros((frames,2))
    phase = np.arctan2(model['mean'][:,1::2],model['mean'][:,0::2])
    for start in range(0,frames,256):
        n = min(256,frames-start);u = np.arange(n)/256
        value = model['mean'][None,:,:]+left[None,:,:]+u[:,None,None]*(right-left)[None,:,:]
        amplitude = np.hypot(value[:,:,0::2],value[:,:,1::2])
        carrier = np.cos(2*np.pi*np.arange(start,start+n)[:,None,None]*
            np.arange(1,h+1)[None,:,None]/1024+phase[None,:,:])
        wave = amplitude*carrier
        output[start:start+n] = wave.sum(axis=1)
        high[start:start+n] = (wave*mask[None,:,None]).sum(axis=1)
        left=right;advance();right=coefficients()
    return output,high,phase
