"""Generic independent OSC core; amplitude-only modulation, no source-ID paths."""
import numpy as np
from idle_modal_v1.modal import render as original_render
from .envelope import states,gains


def render(modal,model,frames,rate,seed,amount=0.,ratio=1.):
    if not np.isfinite(ratio) or ratio<=0:raise ValueError('Positive finite pitch ratio required')
    state,normal=states(model,frames,seed);gain=gains(model,state,frames,amount)
    if amount==0:return original_render(modal,frames,rate,ratio),state,normal
    frequencies=np.asarray(modal['frequencies_hz'])*ratio
    if frequencies.max()>=rate/2:raise ValueError('Pitch exceeds Nyquist')
    amplitude=np.asarray(modal['amplitude_LR']);phase=np.asarray(modal['initial_phase_LR'])
    if gain.shape!=(frames,len(frequencies)):raise ValueError('Envelope/modal dimension mismatch')
    out=np.zeros((frames,2))
    for start in range(0,frames,8192):
        stop=min(frames,start+8192);t=np.arange(start,stop)/rate
        angle=2*np.pi*np.remainder(t[:,None]*frequencies,1.)
        for channel in range(2):
            out[start:stop,channel]=np.sum(np.cos(angle+phase[:,channel])*amplitude[:,channel]*gain[start:stop],axis=1)
    return out,state,normal
