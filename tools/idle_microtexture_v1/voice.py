"""Existing independent OSC and spectral filters; optional fresh detail gains."""
import numpy as np
from scipy import signal
from fixed_source_v1.voice import render as fixed_render
from modal_texture_v1.envelope import states,gains
from sustain_osc_v1.oracle import Gaussian


def render(profile,model,indices,frames,seed,amount):
    baseline,main,_=fixed_render(profile,frames,seed,amount=0)
    state,normal=states(model,frames,seed);gain=gains(model,state,frames,amount)
    if amount==0:return baseline,main,baseline-main,state,normal
    out=np.zeros_like(main);count=frames+profile['warmup_frames']
    for i,kernel in enumerate(profile['kernels']):
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
        noise=np.fromiter((rng.next() for _ in range(count)),dtype=float,count=count)
        stream=signal.oaconvolve(noise,kernel['taps'])[profile['warmup_frames']:count]*kernel['gain']
        if i in indices:stream*=gain[:,indices.index(i)]
        out+=stream[:,None]*np.array([[1.,kernel['right_over_left']]])
    return main+out,main,out,state,normal
