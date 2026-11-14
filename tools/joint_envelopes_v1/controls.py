"""Deterministic full-band stereo envelopes, not recorded waveform loops."""
import numpy as np


def cases(plan):
    known = plan['known'];rate = plan['measurement']['rate']
    t = np.arange(round(rate*known['seconds']))/rate
    for name in known['cases']:
        envelope = np.ones((len(t), 4, 2))
        if name == 'zero':
            envelope[:] = 0
        elif name == 'shared_AM4Hz':
            envelope[:] = (1+.4*np.cos(2*np.pi*4*t))[:, None, None]
        elif name == 'differential_AM':
            for b in range(4):
                envelope[:, b, 0] = (1+.1*t)*(1+.3*np.cos(2*np.pi*(2+b)*t+.2*b))
                envelope[:, b, 1] = (1+.04*t)*(1+.25*np.sin(2*np.pi*(3+b)*t+.4*b))
        audio = np.zeros((len(t), 2))
        for b, freq in enumerate(known['carrier_hz']):
            phase = 2*np.pi*(freq*t+(50*t*t if name == 'rising_carriers' else 0))
            for c in range(2):
                amplitude = known['amplitude_L'][b]*(1 if c == 0 else known['amplitude_R_ratio'])
                offset = 0 if c == 0 else known['phase_R'][b]
                audio[:, c] += amplitude*envelope[:, b, c]*np.cos(phase+offset)
        yield name, audio, envelope
