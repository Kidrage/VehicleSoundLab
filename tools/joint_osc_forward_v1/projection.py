"""Exact linear native-gain to complex window-coefficient response."""
import numpy as np
from idle_phase_amplitude_v1.observe import observe

FRAMES=9600
STARTS=np.arange(12000,122401,960)
SELECTED=np.array([1,2,4])


def compile_response(spec,phasors,cosine,base):
    assert len(phasors)==144000
    t=np.arange(len(phasors))/48000
    carrier=np.exp(2j*np.pi*t[:,None]*spec['frequencies']);carrier[:,SELECTED]=phasors
    A=np.column_stack((carrier.real,carrier.imag,np.ones(len(t))))
    weight=.5-.5*np.cos(2*np.pi*np.arange(FRAMES)/FRAMES)
    indices=np.r_[SELECTED,SELECTED+13];unit=np.eye(A.shape[1])[:,indices]
    responses=[];constant=[]
    for start in STARTS:
        slab=A[start:start+FRAMES];weighted=slab*weight[:,None]
        selected=np.linalg.solve(slab.T@weighted,unit).T@weighted.T
        complex_rows=selected[:3]-1j*selected[3:]
        responses.append(complex_rows[:,:,None]*cosine[start:start+FRAMES][None,:,:]*spec['amplitude'][SELECTED])
        constant.append(complex_rows@base[start:start+FRAMES])
    return dict(response=np.array(responses),constant=np.array(constant),starts=STARTS.copy())


def apply(cache,gain):
    windows=np.array([gain[first:first+FRAMES] for first in cache['starts']])
    return cache['constant']+np.einsum('wjtm,wtm->wj',cache['response'],windows,optimize=True)


def derivative(cache,jacobian):
    return np.array([apply(cache,d)-cache['constant'] for d in jacobian])


def measure(audio,spec,phasors):
    return observe(np.column_stack((audio,audio)),spec['frequencies'],phasors)


def simple_windows(gain):
    weight=.5-.5*np.cos(2*np.pi*np.arange(FRAMES)/FRAMES);weight/=weight.sum()
    mean=np.array([weight@gain[j:j+FRAMES] for j in STARTS])
    logmean=np.exp(np.array([weight@np.log(gain[j:j+FRAMES]) for j in STARTS]))
    return mean,logmean
