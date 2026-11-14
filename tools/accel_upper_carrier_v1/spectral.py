"""Native four-coordinate covariance spectral factor and post-gain/filter/Welch budgets."""
import numpy as np
from scipy import signal

RATE=48000
MIX=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]])


def measure(audio,size=12000):
    starts=np.arange(0,len(audio)-size+1,size//2);window=signal.windows.hann(size,sym=False)
    F=np.array([np.fft.rfft((audio[s:s+size]-audio[s:s+size].mean(axis=0))*window[:,None],axis=0) for s in starts])
    factor=np.full(size//2+1,2.);factor[[0,-1]]=1
    C=np.einsum('wfi,wfj->fij',F.conj(),F)/len(starts)*factor[:,None,None]/(RATE*np.dot(window,window))
    return C,starts


def factor(C,size):
    one=np.full(size//2+1,2.);one[[0,-1]]=1;T=C*RATE/one[:,None,None]
    asym=float(abs(T-T.conj().transpose(0,2,1)).max());scale=float(abs(T).max());assert asym<=1e-12*scale if scale else asym==0
    eigen,Q=np.linalg.eigh(T);maximum=np.max(abs(eigen),axis=1);negative=-np.minimum(eigen[:,0],0)
    assert np.all(negative<=1e-12*maximum)
    corrected=np.maximum(eigen,0);root=np.einsum('fik,fk,fjk->fij',Q,np.sqrt(corrected),Q.conj())
    H=root.conj();edge=float(abs(H[[0,-1]].imag).max());assert edge<=1e-12*scale**.5 if scale else edge==0
    h=np.roll(np.fft.irfft(H,n=size,axis=0),size//2,axis=0)
    return h,dict(negative_roundoff_eigenvalues=int(np.sum(eigen<0)),maximum_negative_relative=float(np.max(np.divide(negative,maximum,out=np.zeros_like(negative),where=maximum>0))),
                  zero_eigenvalues_preserved=int(np.sum(corrected==0)),source_PCM_stored=False)


def covariance(h,padded=65536):
    n=len(h);assert padded>=2*n-1;H=np.fft.fft(h,n=padded,axis=0)
    C=np.einsum('fiq,fjq->fij',H.conj(),H);r=np.fft.ifft(C,axis=0).real
    return np.arange(1-n,n),np.concatenate((r[-(n-1):],r[:n])) if n>1 else r[:1]


def density(lags,cov,size,aperture=None):
    weighted=cov
    if aperture is not None:
        window=signal.windows.hann(aperture,sym=False);ac=signal.correlate(window,window,mode='full',method='fft')/np.dot(window,window)
        weights=np.zeros(len(lags));inside=abs(lags)<aperture;weights[inside]=ac[lags[inside]+aperture-1]
        weighted=cov*weights[:,None,None]
    folded=np.zeros((size,*cov.shape[1:]));np.add.at(folded,lags%size,weighted)
    C=np.fft.fft(folded,axis=0)[:size//2+1];one=np.full(size//2+1,2.);one[[0,-1]]=1
    if aperture is not None:
        assert aperture==size and size>4
        # Exact constant detrend: a periodic Hann has nonzero DFT only at 0,+/-1.
        # The correction is not silently omitted at DC/first bin.
        support=np.arange(1-size,size);R=np.zeros((len(support),*cov.shape[1:]));inside=(lags>=support[0])&(lags<=support[-1])
        R[lags[inside]-support[0]]=cov[inside];prefix=np.concatenate((np.zeros((1,*R.shape[1:])),np.cumsum(R,axis=0)))
        u=np.arange(size);row_sum=prefix[2*size-1-u]-prefix[size-1-u]
        mean_cov=np.einsum('n,nij->ij',size-abs(support),R)/size**2
        for k,Wk in [(0,size/2),(1,-size/4)]:
            B=np.einsum('n,nij->ij',window*np.exp(2j*np.pi*k*u/size),row_sum)/size
            C[k]+=(-Wk*B-Wk*B.conj().T+Wk**2*mean_cov)/np.dot(window,window)
    return C*one[:,None,None]/RATE


def apply_gain(lags,cov,Gamma,tau):
    rho=np.exp(-abs(lags)/(RATE*tau));mean_correction=(np.diag(Gamma)[:,None]+np.diag(Gamma)[None,:])/2
    moment=np.exp(rho[:,None,None]*Gamma[None]-mean_correction[None])
    return cov*moment


def refilter(lags,cov,impulse,padded=65536):
    extent=int(max(abs(lags)))+len(impulse)-1;assert padded>=2*extent+1
    folded=np.zeros((padded,*cov.shape[1:]));np.add.at(folded,lags%padded,cov)
    C=np.fft.fft(folded,axis=0);H=np.fft.fft(impulse,n=padded,axis=0)
    C*=H.conj()[:,:,None]*H[:,None,:];r=np.fft.ifft(C,axis=0).real
    return np.arange(-extent,extent+1),np.concatenate((r[-extent:],r[:extent+1]))


def stereo(C):return np.einsum('ai,fij,bj->fab',MIX,C,MIX)


def summaries(C,size):
    hz=np.fft.rfftfreq(size,1/RATE);rows=[];S=stereo(C);df=RATE/size
    for lo,hi in [(0,4000),(4000,8000),(8000,14000),(14000,24000)]:
        mask=(hz>=lo)&((hz<hi) if hi<24000 else (hz<=hi));A=S[mask];P=np.real(A[:,[0,1],[0,1]]);den=P[:,0]*P[:,1]
        valid=(P[:,0]>0)&(P[:,1]>0);coherence=np.zeros(len(A));np.divide(abs(A[:,0,1])**2,den,out=coherence,where=valid)
        powers=P.sum(axis=0)*df;cross=np.sum(A[:,0,1])*df
        norm=cross/np.sqrt(np.prod(powers)) if np.all(powers>0) else 0j
        weight=np.where(valid,P.sum(axis=1),0.);weighted=float(np.dot(coherence,weight)/weight.sum()) if weight.sum()>0 else 0.
        rows.append(dict(band_hz=[lo,hi],coordinate_power=(np.real(C[mask][:,[0,1,2,3],[0,1,2,3]]).sum(axis=0)*df).tolist(),
            stereo_power=powers.tolist(),integrated_normalized_LR=[float(norm.real),float(norm.imag)],power_weighted_MSC=weighted,
            defined_stereo_bins=int(valid.sum()),total_stereo_bins=len(A)))
    return rows
