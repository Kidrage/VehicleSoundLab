"""Existing independent OSC drives a measured smooth POWER law on spectral detail."""
import numpy as np
from scipy import signal
from fixed_source_v1.voice import render as fixed_render
from sustain_osc_v1.oracle import Gaussian
from .model import gain


def render(profile,model,frames,seed,amount):
    baseline,main,_=fixed_render(profile,frames,seed,amount=0)
    index=model['modal_indices'];frequencies=np.asarray(profile['modal']['frequencies_hz'])[index]
    phase=np.asarray(profile['modal']['initial_phase_LR'])[index,0]
    t=np.arange(frames)/profile['sample_rate']
    phasors=np.exp(1j*(2*np.pi*t[:,None]*frequencies+phase))
    gains=gain(model,phasors,amount)
    if amount==0:return baseline,main,baseline-main,gains
    detail=np.zeros_like(main);count=frames+profile['warmup_frames']
    for i,kernel in enumerate(profile['kernels']):
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
        noise=np.fromiter((rng.next() for _ in range(count)),dtype=float,count=count)
        stream=signal.oaconvolve(noise,kernel['taps'])[profile['warmup_frames']:count]*kernel['gain']
        if i>=2:stream*=gains[:,i-2]
        detail+=stream[:,None]*np.array([[1.,kernel['right_over_left']]])
    return main+detail,main,detail,gains

