"""TRAIN-only joint positive amplitude statistics; no stored recording trajectory."""
import numpy as np
from scipy import signal

SEED_KEY=0xA1D1E5A39B47
RATE=50
STEP=960


def covariance(taps,maximum=50):
    """C[k]=E(x[n] x[n+k]^T); signed lags use its transpose."""
    h=np.asarray(taps)
    return np.array([np.einsum('toi,tpi->op',h[:len(h)-k],h[k:]) for k in range(maximum+1)])


def fit(x):
    x=np.asarray(x);assert x.shape==(116,3)
    assert abs(x.mean(axis=0)).max()<1e-12
    window=signal.windows.hann(32,sym=False)
    sections=np.array([x[j:j+32]*window[:,None] for j in range(0,len(x)-31,16)])
    assert len(sections)==6
    z=np.fft.rfft(sections,n=64,axis=1)
    spectrum=np.einsum('wfi,wfj->fij',z,z.conj())/(len(z)*sum(window**2))
    factors=[];minimum=[]
    for s in spectrum:
        eig,v=np.linalg.eigh(s);minimum.append(float(eig.min()))
        if eig.min() < -1e-12:raise ValueError('Indefinite empirical outer-product spectrum')
        factors.append((v*np.sqrt(np.maximum(eig,0.)))@v.conj().T)
    h=np.roll(np.fft.irfft(factors,n=64,axis=0),32,axis=0)
    target=x.T@x/len(x);actual=covariance(h,0)[0]
    transform=np.linalg.solve(np.linalg.cholesky(actual).T,np.linalg.cholesky(target).T).T
    h=np.einsum('op,tpi->toi',transform,h)
    curves=covariance(h)
    assert abs(curves[0]-target).max()<1e-12
    return dict(schema='vsl.idle-phase-aware-amplitude/1',selected_modes=[1,2,4],node_rate=RATE,
                taps=h.tolist(),training_covariance=target.tolist(),predicted_node_covariance_lags=curves.tolist(),
                spectral_frames=32,spectral_hop=16,spectral_fft=64,spectral_windows=len(sections),
                minimum_spectral_eigenvalue=min(minimum),covariance_residual=float(abs(curves[0]-target).max()),
                phase_amplitude_independent_hypothesis=True,recorded_trajectory=False,
                normalization='g=exp(s*x-s^2*diag(C0)); expected squared gain one, not per-take normalization',
                scope='Acoustic phase-aware window magnitude statistics; not physical combustion AM')


def weights(u):
    u=np.asarray(u)
    return np.column_stack((-.5*u+u*u-.5*u**3,1-2.5*u*u+1.5*u**3,
                            .5*u+2*u*u-1.5*u**3,-.5*u*u+.5*u**3))


def interpolation(model):
    """All native fractional covariances include cross-node and cross-mode terms."""
    c=covariance(model['taps'],3);w=weights(np.arange(STEP)/STEP)
    r=np.zeros((STEP,3,3))
    for i in range(4):
        for j in range(4):
            k=j-i;lag=c[k] if k>=0 else c[-k].T
            r+=w[:,i,None,None]*w[:,j,None,None]*lag
    root=np.linalg.cholesky(c[0]);T=np.empty_like(r)
    for i,v in enumerate(r):T[i]=np.linalg.solve(np.linalg.cholesky(v).T,root.T).T
    error=float(abs(np.einsum('fij,fjk,flk->fil',T,r,T)-c[0]).max())
    assert error<1e-12 and abs(T[0]-np.eye(3)).max()<1e-12
    return dict(weights=w,transform=T,raw_covariance=r,covariance=c[0],residual=error)


def nodes(model,seed,seconds):
    h=np.array(model['taps']);count=int(np.ceil(seconds*RATE))+5;warm=len(h)-1
    rng=np.random.Generator(np.random.PCG64(seed^SEED_KEY));white=rng.standard_normal((count+warm,3))
    out=np.zeros((count,3))
    for i in range(3):
        for j in range(3):out[:,i]+=signal.oaconvolve(white[:,j],h[:,i,j])[warm:warm+count]
    return out


def native(values,table,start,count):
    frame=np.arange(start,start+count);k=frame//STEP;f=frame%STEP
    raw=sum(table['weights'][f,i,None]*values[k+i+1] for i in range(4))
    return np.einsum('fij,fj->fi',table['transform'][f],raw)


def gains(x,amount,cov):
    return np.exp(amount*x-amount*amount*np.diag(cov))


def known():
    # Delayed shared innovation distinguishes signed cross-lag from same-time covariance.
    h=np.zeros((8,3,3));h[0,0,0]=.7;h[2,1,0]=.4;h[0,1,1]=.5;h[0,2,2]=.3
    c=covariance(h,3)
    assert abs(c[0]-np.diag([.49,.41,.09])).max()<1e-14
    assert abs(c[2,0,1]-.28)<1e-14 and abs(c[2,1,0])<1e-14
    table=interpolation(dict(taps=h.tolist()))
    # Closed-form Gaussian MGF for E(g^2), not a finite random Monte Carlo estimate.
    v=np.diag(c[0]);errors=[]
    for amount in [0.,.5,1.]:errors.append(float(abs(np.exp(-2*amount**2*v+(.5*(2*amount)**2)*v)-1).max()))
    assert max(errors)<1e-14
    return dict(delayed_covariance_error=float(abs(c[2,0,1]-.28)),
                full_fractional_covariance_error=table['residual'],lognormal_expected_squared_gain_error=max(errors))
