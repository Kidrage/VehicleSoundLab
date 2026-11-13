"""Joint phase texture from TRAIN cross spectra; finite filters, no source timeline."""
import numpy as np
from scipy import signal


def fit(chart_model, source, rate=48000):
    w=np.column_stack((source[:,2]*source[:,1].conj()*source[:,0].conj(),source[:,0]**3*source[:,1].conj()**2))
    center=np.angle(w.mean(axis=0));native=np.angle(w*np.exp(-1j*center))
    if abs(native).max()>=np.pi-.05:raise ValueError('Unresolved coordinate chart')
    x=signal.resample_poly(native,1,rate//200,window=('kaiser',8.6),padtype='line')
    offset=x.mean(axis=0);x-=offset
    window=signal.windows.hann(128,sym=False)
    sections=np.array([x[j:j+128]*window[:,None] for j in range(0,len(x)-127,64)])
    fft=np.fft.rfft(sections,n=256,axis=1)
    spectrum=np.einsum('wfi,wfj->fij',fft,fft.conj())/(len(sections)*np.sum(window**2))
    eigenvectors=[];factors=[];minimum=[]
    for s in spectrum:
        eig,v=np.linalg.eigh(s);minimum.append(float(eig.min()))
        if eig.min() < -1e-12:raise ValueError('Invalid empirical cross spectrum')
        # Only roundoff-negative eigenvalues of an explicit sum of outer products are zeroed.
        factors.append((v*np.sqrt(np.maximum(eig,0.)))@v.conj().T)
    h=np.roll(np.fft.irfft(factors,n=256,axis=0),128,axis=0)
    target=x.T@x/len(x);actual=np.einsum('toi,tpi->op',h,h)
    transform=np.linalg.solve(np.linalg.cholesky(actual),np.eye(2))
    transform=np.linalg.cholesky(target)@transform
    h=np.einsum('op,tpi->toi',transform,h)
    residual=float(abs(np.einsum('toi,tpi->op',h,h)-target).max())
    assert residual<1e-12
    model={k:v for k,v in chart_model.items() if k in ['carrier_phase_rad','carrier_hz','source_frames','scope']}
    model.update(schema='vsl.idle-phase-spectral-statistics/1',node_rate=200,
        coordinate_center=(center+offset).tolist(),taps=h.tolist(),kernel_shape=list(h.shape),
        training_covariance=target.tolist(),covariance_residual=residual,
        spectral_windows=len(sections),spectral_frames=128,spectral_hop=64,spectral_fft=256,
        minimum_spectral_eigenvalue=min(minimum),PCM_or_phase_trajectory=False,
        scope='Finite joint Gaussian acoustic phase texture; not measured engine coupling')
    return model


def nodes(model,seed,seconds):
    count=int(np.ceil(seconds*model['node_rate']))+5
    taps=np.asarray(model['taps']);warm=len(taps)-1
    rng=np.random.Generator(np.random.PCG64(seed ^ 0x5E1A3C897AB4))
    white=rng.standard_normal((count+warm,2))
    out=np.zeros((count,2))
    for i in range(2):
        for j in range(2):
            out[:,i]+=signal.oaconvolve(white[:,j],taps[:,i,j])[warm:warm+count]
    return out+model['coordinate_center']


def known():
    # Known delayed cross-channel filter: cross spectrum keeps phase, not only PSD magnitudes.
    h=np.zeros((16,2,2));h[0,0,0]=.7;h[2,1,0]=.4;h[0,1,1]=.5
    S=np.einsum('foi,fpi->fop',np.fft.rfft(h,axis=0),np.fft.rfft(h,axis=0).conj())
    expected=np.array([[.49,.28*np.exp(1j*2*np.pi*2/16)],[.28*np.exp(-1j*2*np.pi*2/16),.41]])
    err=float(abs(S[1]-expected).max());assert err<1e-14
    # Verify stationary covariance includes every causal input, with independent input channels.
    covariance=np.einsum('toi,tpi->op',h,h)
    assert abs(covariance-np.diag([.49,.41])).max()<1e-14
    return dict(known_delayed_cross_spectrum_error=err,finite_filter_covariance=True,
                model_has_no_feedback_poles=True)
