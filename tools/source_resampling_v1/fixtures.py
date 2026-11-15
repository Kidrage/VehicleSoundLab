"""Analytic source tones with common constant/swept fractional-time queries."""
import numpy as np


def fixtures():
    n = np.arange(38400)
    frequencies = np.array([0., 100., 1000., 5000., 9000., 13000., 13950., 14000.])
    coefficients = np.array([[.02, -.01], [.13, .09], [.03, -.05j],
        [.02j, .04], [.01, .015j], [.008j, -.004], [.004, .006j], [.003j, .002]], complex)
    cycles = np.arange(12289)/1024
    clocks = dict(constant=.25+cycles/60,
        swept=.25+2*cycles/(58+np.sqrt(58**2+2*40*cycles)))
    for clock, positions in clocks.items():
        for name, scale in (('stereo', 1.), ('weak', 1e-6)):
            yield clock+'_'+name, frequencies, coefficients*scale, positions, n
    yield 'mono', frequencies, np.repeat(coefficients[:, :1], 2, axis=1), clocks['swept'], n
    silent = coefficients.copy(); silent[:, 1] = 0
    yield 'silent_right', frequencies, silent, clocks['swept'], n
    yield 'zero', frequencies, coefficients*0, clocks['swept'], n
    # Different basis terms cancel exactly in both channels; retain terms
    # separately rather than normalizing to a near-zero realized waveform.
    yield 'cancellation', np.array([5000., 5000., 13950.]), np.array(
        [[.1, .08j], [-.1+1e-8, -.08j+2e-8], [1e-8j, -1e-8]]), clocks['swept'], n


def evaluate(times, frequencies, coefficients, taps=None):
    gain = np.ones(len(frequencies))
    if taps is not None:
        offsets = np.arange(len(taps))-(len(taps)-1)/2
        gain = np.cos(2*np.pi*frequencies[:, None]*offsets[None]/48000)@taps
    return np.real(np.exp(2j*np.pi*np.asarray(times)[:, None]*frequencies[None])
        @(coefficients*gain[:, None]))
