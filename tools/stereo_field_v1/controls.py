"""Known stationary/reversing binaural transfer, not an engine or an HRTF."""
import numpy as np


def cases(plan,seed):
    rate=plan['sample_rate'];frames=rate*plan['known_seconds'];rng=np.random.default_rng(seed)
    shared,independent=rng.normal(size=(2,frames))
    yield 'mono',np.column_stack((shared,shared))
    yield 'independent',np.column_stack((shared,independent))
    hz=np.fft.rfftfreq(frames,1/rate)
    gain=np.exp(.5*np.sin(2*np.pi*hz/1600))
    angle=-2*np.pi*hz*plan['known_delay_seconds']
    rho=plan['known_coherence']
    def transfer(sign):
        h=gain**sign
        return np.fft.irfft(h*(rho*np.exp(1j*sign*angle)*np.fft.rfft(shared)
            +np.sqrt(1-rho*rho)*np.fft.rfft(independent)),n=frames)
    positive=transfer(1)
    yield 'coloured_delay',np.column_stack((shared,positive))
    negative=transfer(-1);positive[frames//2:]=negative[frames//2:]
    yield 'reversing',np.column_stack((shared,positive))
