"""Direct log-magnitude moments, preserving the caller's fixed harmonic phase."""
import numpy as np


def fit(audio, harmonics=300, components=12):
    starts = np.arange(0,len(audio)-1024+1,256)
    k = np.arange(1,harmonics+1)
    z = np.array([np.fft.rfft(audio[at:at+1024],axis=0)[k]*2/1024 for at in starts])
    rms = np.sqrt(np.mean(abs(z)**2,axis=0))
    floor = np.maximum(rms*1e-6,1e-20)
    logs = np.log(np.maximum(abs(z),floor[None,:]))
    centered = (logs-logs.mean(axis=0)).reshape(len(starts),-1)
    u,s,v = np.linalg.svd(centered,full_matrices=False)
    rank = int(np.sum(s>max(float(s[0])*1e-7,1e-12)))
    count = min(components,rank,len(starts)-1)
    basis = v[:count]*(s[:count,None]/np.sqrt(len(starts)-1))
    scores = u[:,:count]*np.sqrt(len(starts)-1)
    rho = np.clip(np.sum(scores[1:]*scores[:-1],axis=0)/np.maximum(np.sum(scores[:-1]**2,axis=0),1e-30),-.95,.95)
    residual = (centered-scores@basis).reshape(len(starts),harmonics,2)
    root, rr = [],[]
    for h in range(harmonics):
        r = residual[:,h]
        eigen,vectors = np.linalg.eigh(r.T@r/(len(r)-1))
        root.append(vectors@np.diag(np.sqrt(np.maximum(eigen,0))))
        rr.append(float(np.clip(np.sum(r[1:]*r[:-1])/max(float(np.sum(r[:-1]**2)),1e-30),-.95,.95)))
    return dict(rms=rms,basis=basis.reshape(count,harmonics,2).transpose(1,0,2),
        rho=rho,root=np.array(root),residual_rho=np.array(rr)),dict(
        observation_frames=len(starts),components=count,harmonics=harmonics,
        log_magnitude_variance_fraction=float(np.sum(s[:count]**2)/max(float(np.sum(s*s)),1e-30)),
        floor_relative_rms=1e-6,phase_fitted=False,trajectory_stored=False)


def render(model, phase, frames, seed, mask):
    """New Gaussian AR states; normalization keeps expected squared magnitude."""
    rng = np.random.default_rng(seed)
    h,k = model['basis'].shape[:2]
    pc = rng.normal(size=k);residual = rng.normal(size=(h,2))
    rho,rr = model['rho'],model['residual_rho']
    basis = model['basis'];root = model['root']

    def coefficients():
        return np.einsum('hkc,k->hc',basis,pc)+np.einsum('hcj,hj->hc',root,residual)

    def advance():
        nonlocal pc,residual
        pc = rho*pc+np.sqrt(1-rho*rho)*rng.normal(size=k)
        residual = rr[:,None]*residual+np.sqrt(1-rr*rr)[:,None]*rng.normal(size=(h,2))

    left = coefficients();advance();right = coefficients()
    output = np.zeros((frames,2))
    for start in range(0,frames,256):
        n = min(256,frames-start);u = np.arange(n)/256
        value = left[None,:,:]+u[:,None,None]*(right-left)[None,:,:]
        variance = np.einsum('hkc,nk->nhc',basis*basis,
            (1-u[:,None])**2+u[:,None]**2+2*u[:,None]*(1-u[:,None])*rho[None,:])
        residual_variance = np.sum(root*root,axis=2)
        variance += residual_variance[None,:,:]*((1-u[:,None,None])**2+u[:,None,None]**2+
            2*u[:,None,None]*(1-u[:,None,None])*rr[None,:,None])
        amplitude = model['rms'][None,:,:]*np.exp(value-variance)
        carrier = np.cos(2*np.pi*np.arange(start,start+n)[:,None,None]*
            np.arange(1,h+1)[None,:,None]/1024+phase[None,:,:])
        output[start:start+n] = np.sum(amplitude*carrier*mask[None,:,None],axis=1)
        left=right;advance();right=coefficients()
    return output
