"""One declared source recipe. Stochastic details stay separate from modal DNA."""
import math
import numpy as np
from scipy import signal
from sustain_osc_v1.oracle import Gaussian
from idle_modal_v1.modal import render as modal_render
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

MASK = (1 << 64)-1


def power(profile, law, frames, rate):
    t = np.arange(frames)/rate
    modes = profile['modal']; indices = [1, 2, 4]
    frequencies = np.asarray(modes['frequencies_hz'])[indices]
    phases = np.asarray(modes['initial_phase_LR'])[indices, 0]
    z = np.exp(1j*(2*np.pi*np.remainder(t[:, None]*frequencies, 1.)+phases))
    q = predict(law, matrix(z, hop=1, trim=0))
    assert np.all(q.min(axis=0) >= law['bounds']['power_lower'])
    assert np.all(q.max(axis=0) <= law['bounds']['power_upper'])
    return q


def voices(profile, law, old_probability, new_probability, seed, frames, rate):
    main = modal_render(profile['modal'], frames, rate)
    q = power(profile, law, frames, rate)
    detail = {mode: np.zeros_like(main) for mode in ['static', 'sparse', 'post']}
    warmup = profile['warmup_frames']; count = frames+warmup; events = []
    for index, kernel in enumerate(profile['kernels']):
        key = seed ^ (0x9E3779B97F4A7C15*(index+1) & MASK)
        rng = Gaussian(key)
        gaussian = np.fromiter((rng.next() for _ in range(count)), float, count=count)
        noises = {'static': gaussian}
        event = dict(index=index)
        if index < 2:
            noises.update(sparse=gaussian, post=gaussian)
        else:
            marks = Gaussian(key ^ 0xD1B54A32D192ED03)
            amp = Gaussian(key ^ 0x94D049BB133111EB)
            uniform = np.empty(count); normal = np.empty(count)
            for j in range(count):
                uniform[j] = marks.uniform()/2**53; normal[j] = amp.next()
            for mode, probabilities in [('sparse', old_probability), ('post', new_probability)]:
                p = probabilities[index-2]; on = uniform < p
                noises[mode] = np.where(on, normal/math.sqrt(p), 0.)
                event[mode] = int(on.sum())
        for mode, noise in noises.items():
            y = signal.oaconvolve(noise, np.asarray(kernel['taps']))[warmup:count]*kernel['gain']
            if mode == 'post' and index >= 2: y *= np.sqrt(q[:, index-2])
            detail[mode] += y[:, None]*np.array([[1., kernel['right_over_left']]])
        events.append(event)
    return main, detail, q, events
