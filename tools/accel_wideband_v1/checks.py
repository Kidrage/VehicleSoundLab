"""Known moving/fixed/missing/gain/noise dictionaries; not clock extraction."""
import numpy as np
from .chirplet import transform,inventory
from .coverage import decomposition


def matches(measured,truth):
    return sum(sum(abs(f-t)<=2 for f in measured)==1 for t in truth)


def controls():
    rate=48000;n=12000;t=(np.arange(n)-n/2)/rate;root=60.613
    frequency=root*np.arange(5,101);phase=np.random.default_rng(55371).uniform(-np.pi,np.pi,len(frequency))
    def tones(alpha,missing=False):
        keep=np.ones(len(frequency),dtype=bool)
        if missing:keep[55]=False
        left=np.sum(.01*np.cos(2*np.pi*(t[:,None]+.5*alpha*t[:,None]**2)*frequency[None,:]+phase)[...,keep],axis=1)
        return np.column_stack((left,.73*left))
    audio=tones(.05);out={};arrays={}
    for name,signal,alpha in [('moving_native',audio,0.),('moving_compensated',audio,.05),
        ('moving_wrong_sign',audio,-.05),('fixed_native',tones(0),0.),('fixed_compensated',tones(0),.05),
        ('missing_compensated',tones(.05,True),.05),('gain_compensated',audio*.17,.05),
        ('noise_compensated',np.random.default_rng(917431).normal(0,.02,(n,2)),.05)]:
        f,z=transform(signal,alpha);inv=inventory(f,z);truth=frequency[(frequency>=2200)&(frequency<7000)]
        out[name]=dict(alpha=alpha,inventory=inv,high_true_matches=matches(inv['frequency_hz'],truth),high_truth_count=len(truth))
        arrays[name]=dict(audio=signal,frequency=f,transform=z)
    positive=out['moving_compensated'];native=out['moving_native']
    assert positive['high_true_matches']>=.9*positive['high_truth_count']
    assert positive['high_true_matches']>native['high_true_matches']
    assert positive['inventory']['bin']==out['gain_compensated']['inventory']['bin']
    assert not any(abs(v-frequency[55])<=2 for v in out['missing_compensated']['inventory']['frequency_hz'])
    # Zero-alpha direct dictionary has the FFT's known centered time origin.
    z=arrays['fixed_native']['transform'];f=arrays['fixed_native']['frequency']
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    fft=np.fft.rfft(tones(0)*window[:,None],axis=0)[:len(f)]
    expected=fft*np.exp(2j*np.pi*f*n/(2*rate))[:,None]
    err=float(abs(z-expected).max());assert err<1e-9
    # Exact power identity includes destructive interference; model/source may exceed1.
    x=np.column_stack((np.cos(2*np.pi*320*t),.7*np.cos(2*np.pi*320*t)))
    parts,error=decomposition(x,x*1.5,[[300,400]])
    assert error<1e-12 and parts['interference'][0][0]<0 and parts['model'][0][0]>parts['source'][0][0]
    return dict(cases=out,zero_dictionary_fft_error=err,power_identity_error=error,
        residual_not_physical_noise=True,dictionary_not_Parseval_PSD=True,engine_phase_estimator_qualified=False),arrays
