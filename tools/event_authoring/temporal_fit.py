"""Opt-in acoustic band envelopes; no new carriers, source separation or RPM claim."""
from copy import deepcopy
import numpy as np
from scipy import optimize,signal
from .model import attack
from .contract import validate
from .measure import EDGES


def band_curves(x):
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    f,t,p=signal.spectrogram(x,48000,window='hann',nperseg=2048,noverlap=1808,axis=0,
        detrend=False,scaling='density',mode='psd')
    return t,np.array([p[(f>=lo)&(f<hi)].sum(axis=0).mean(axis=0)*(f[1]-f[0]) for lo,hi in EDGES])


def fit(profile,x,background):
    """Fit normalized cumulative energy, then leave finite-response gains to caller."""
    p=deepcopy(profile);t,raw=band_curves(x);_,bg=band_curves(background)
    excess=np.maximum(raw-bg.mean(axis=1)[:,None],0)
    rows=[];duration=len(x)/48000
    # Match the finite Hann energy footprint rather than a pointwise envelope.
    sample_t=np.arange(len(x))/48000
    window=signal.windows.hann(2048,sym=False)**2;window/=window.sum()
    def shape(a,tau):
        env=attack(sample_t,p['attack_seconds'])*attack(sample_t,a)
        if not p['gated']:env*=np.exp(-sample_t/tau)
        end_frame=int(np.ceil(p['duration_seconds']*48000))
        left=np.clip((end_frame-np.arange(len(x)))/(48000*p['release_seconds']),0,1)
        env*=left*left*(3-2*left)
        return signal.fftconvolve(env*env,window[::-1],mode='valid')[::240]
    def cdf(y):return np.cumsum(y)/max(float(y.sum()),1e-30)
    for index,(lo,hi) in enumerate(EDGES):
        target=excess[index];old=p['bands'][index]
        if target.sum()<=1e-20:
            rows.append(dict(hz=[lo,hi],fitted=False,reason='No positive acoustic excess'));continue
        objective=cdf(target)
        def residual(v):return cdf(shape(v[0],old['decay_seconds'] if p['gated'] else v[1]))-objective
        initial=[max(.0005,min(duration,2.,float(t[np.argmax(target)]))),old['decay_seconds']]
        bounds=([0,.002],[min(2.,duration),10.])
        if p['gated']:initial=initial[:1];bounds=([0],[min(2.,duration)])
        result=optimize.least_squares(residual,initial,bounds=bounds,
            max_nfev=120,ftol=1e-9,xtol=1e-9,gtol=1e-9)
        a=float(result.x[0]);tau=old['decay_seconds'] if p['gated'] else float(result.x[1])
        # A single smooth envelope cannot reproduce multiple acoustic bursts.
        # Retain that mismatch in the report, never claim complete reconstruction.
        old_error=float(np.sqrt(np.mean((cdf(shape(old['attack_seconds'],old['decay_seconds']))-objective)**2)))
        new_error=float(np.sqrt(np.mean(residual(result.x)**2)))
        old['attack_seconds']=a
        if not p['gated']:old['decay_seconds']=tau
        assigned=[]
        for i,m in enumerate(p['modes']):
            if lo<=m['hz']<hi:
                m['attack_seconds']=a
                if not p['gated']:m['decay_seconds']=tau
                assigned.append(i)
        rows.append(dict(hz=[lo,hi],fitted=True,attack_seconds=a,decay_seconds=tau,
            modal_indices=assigned,old_envelope_cdf_rmse=old_error,envelope_cdf_rmse=new_error,
            optimizer_terminated=bool(result.success),evaluations=result.nfev,
            source_peak_seconds=float(t[np.argmax(target)])))
    return validate(p),dict(method='band-attack-v1',bands=rows,
        policy='Fixed 2048-frame Hann power,240-frame hop,mean channel powers; positive background-subtracted curves. Fit one smoothstep attack and nongated exponential decay per existing 60–300/300–1200/1200–4500/4500–14000Hz band to normalized cumulative energy; max120 evaluations. Existing frequencies/phases/carrier counts unchanged. Finite-response gains must be recalibrated afterwards.',
        limitations='An acoustic band envelope is not individual-mode isolation or measured combustion/RPM. Envelope smoothing does not recreate multiple bursts or pitch movement. One crop does not validate another startup. Attack is seconds, independent of the request decay multiplier; gated decay remains unused. Listening acceptance is separate.')
