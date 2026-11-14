"""Analysis-only local coherent projection with explicit overlap and cross-power budget."""
import numpy as np
from scipy import signal
from idle_phase_amplitude_v1.observe import observe
from idle_phase_amplitude_v1.residual import design

SELECTED=np.array([1,2,4])
RATE=48000
BANDS=np.array([[0,30],[30,120],[120,400],[400,1200],[1200,2200],[2200,4000],
                [4000,8000],[8000,14000],[14000,24000.000001]])


def partition(audio,frequencies,phasors):
    """Retain source coefficients only for analysis; this is not a synthesizer."""
    A=design(len(audio),np.asarray(frequencies),phasors)
    local=observe(audio,frequencies,phasors)
    coefficients=local['coefficients'];starts=local['starts'];frames=9600
    w=signal.windows.hann(frames,sym=False);trim=12000
    fullw=signal.windows.hann(len(audio)-2*trim,sym=False)
    slab=A[trim:-trim]
    beta=np.linalg.solve(slab.T@(slab*fullw[:,None]),slab.T@(audio[trim:-trim]*fullw[:,None]))
    variable=np.zeros((len(audio),3),complex);denominator=np.zeros(len(audio));dc=[]
    for row,first in enumerate(starts):
        z=coefficients[row];fitted=A[first:first+frames,:13]@z.real-A[first:first+frames,13:26]@z.imag
        dc.append(float(np.sum((audio[first:first+frames,0]-fitted)*w)/sum(w)))
        variable[first:first+frames]+=w[:,None]*z[SELECTED]
        denominator[first:first+frames]+=w
    lo,hi=int(starts[0]+frames),int(starts[-1])
    assert (lo,hi)==(21600,122400) and np.all(denominator[lo:hi]>0)
    coefficient=variable[lo:hi]/denominator[lo:hi,None]
    static=A[lo:hi]@beta;dynamic=static.copy()
    # Fit is common to both channels only at the selected varying components.
    # Preserve observed interchannel coefficient ratio from the global source fit.
    base=beta[SELECTED]-1j*beta[SELECTED+13]
    ratio=base[:,1]/base[:,0]
    if not np.isfinite(ratio).all() or np.any(abs(base[:,0])==0):raise ValueError('Unresolved stereo coefficient ratio')
    for c in range(2):
        delta=coefficient*(ratio if c else 1)-base[:,c]
        dynamic[:,c]+=np.sum(phasors[lo:hi]*delta,axis=1).real
    return dict(audio=audio[lo:hi],static_main=static,dynamic_main=dynamic,
                static_residual=audio[lo:hi]-static,dynamic_residual=audio[lo:hi]-dynamic,
                global_coefficients=beta,local_coefficients=coefficients,local_dc=np.array(dc),
                starts=starts,denominator=denominator[lo:hi],variable_coefficients=coefficient,
                stereo_ratio=ratio,source_roi_frames=np.array([lo,hi]))


def budget(audio,main,residual,frequencies):
    n=len(audio);window=signal.windows.hann(n,sym=False)
    f=np.fft.rfftfreq(n,1/RATE);factor=np.full(len(f),2.);factor[0]=factor[-1]=1.
    Z=[np.fft.rfft(x*window[:,None],axis=0) for x in [audio,main,residual]]
    spectra=[abs(x)**2 for x in Z]+[2*(Z[1]*Z[2].conj()).real]
    spectra=[s*factor[:,None]/(n*sum(window**2)) for s in spectra]
    result={}
    for name,power in zip(['total','main','residual','cross'],spectra):
        result[name]=np.array([np.sum(power[(f>=lo)&(f<hi)],axis=0) for lo,hi in BANDS])
        result[name+'_near_lines']=np.array([np.sum(power[abs(f-hz)<=10],axis=0) for hz in np.asarray(frequencies)[SELECTED]])
    result['identity_error']=float(abs(result['total']-result['main']-result['residual']-result['cross']).max())
    result['full_band_parseval_error']=float(abs(result['total'].sum(axis=0)-np.sum((audio*window[:,None])**2,axis=0)/sum(window**2)).max())
    assert result['identity_error']<1e-12 and result['full_band_parseval_error']<1e-12
    return result
