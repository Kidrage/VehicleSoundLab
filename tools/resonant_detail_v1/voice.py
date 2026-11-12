"""New continuous excitation through immutable filters, no stored source audio."""
import numpy as np
from scipy import signal
from sustain_osc_v1.oracle import Gaussian
from .envelope import samples

def render(models,frames,seed,plan):
    warm=plan['warmup_frames'];result=[]
    for i,model in enumerate(models):
        # Independent band streams; explicit separation allows a later C port
        # to reproduce innovations using the existing xorshift/BoxMuller rule.
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
        noise=np.fromiter((rng.next() for _ in range(warm+frames)),dtype=float,count=warm+frames)
        x=signal.lfilter([model['sigma']],model['a'],noise)
        x*=samples(model['envelope']['coefficients'],len(x),-warm,plan['cycle_frames'])
        x=signal.sosfilt(np.asarray(model['sos']),x)[warm:]
        result.append(x)
    return np.column_stack(result)
