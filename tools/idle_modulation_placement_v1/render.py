"""Placement diagnostic: same innovations, FIRs and downstream observer filters."""
import itertools
import numpy as np
from scipy import signal


def bank(innovations, taps, amplitude, placement):
    if placement not in ('pre', 'post'):
        raise ValueError('Unknown amplitude placement')
    result = np.zeros(len(innovations))
    for i, kernel in enumerate(taps):
        drive = innovations[:, i]*amplitude[:, i] if placement == 'pre' else innovations[:, i]
        branch = signal.fftconvolve(drive, kernel)[:len(drive)]
        result += branch if placement == 'pre' else branch*amplitude[:, i]
    return result


def powers(seed, taps, amplitude, sos, warmup, frames):
    innovations = np.random.Generator(np.random.PCG64(seed)).standard_normal(amplitude.shape)
    output = []
    for placement in ('pre', 'post'):
        x = bank(innovations, taps, amplitude, placement)
        observed = np.column_stack([signal.sosfilt(s, x)[warmup:warmup+frames] for s in sos])
        output.append((observed**2).reshape(-1, 48, 4).mean(axis=1))
    return np.asarray(output)


def known():
    taps = [np.array([.7, -.2]), np.array([.3, .6])]
    observers = [np.array([.8, .3]), np.array([-.25, .5])]
    n = 8; time = np.arange(n)
    gains = np.column_stack((1+.3*np.sin(.9*time), .8+.2*np.cos(.4*time)))
    binary = np.array(list(itertools.product((-1., 1.), repeat=2*n))).reshape(-1, n, 2)
    results = {}; maximum = 0.
    for placement in ('pre', 'post'):
        # Full impulse basis is exact for any independent unit-variance inputs.
        columns = []
        for address in range(2*n):
            delta = np.zeros((n, 2)); delta.flat[address] = 1
            x = bank(delta, taps, gains, placement)
            columns.append(np.column_stack([np.convolve(x, h)[:n] for h in observers]))
        response = np.asarray(columns); expected = (response**2).sum(axis=0)
        # Local three-sample support has at most six binary variables per time.
        direct = np.zeros((n, 2))
        for at in range(n):
            addresses = [(k, i) for k in range(max(0, at-2), at+1) for i in range(2)]
            for draw in itertools.product((-1., 1.), repeat=len(addresses)):
                noise = np.zeros((n, 2))
                for (k, i), value in zip(addresses, draw): noise[k, i] = value
                x = bank(noise, taps, gains, placement)
                direct[at] += np.array([np.convolve(x, h)[at]**2 for h in observers])/2**len(addresses)
        error = float(abs(expected-direct).max()); maximum = max(maximum, error)
        assert error < 1e-12
        results[placement] = expected.tolist()
    stationary = np.ones_like(gains)*np.array([.8, 1.2])
    noise = binary[173]
    identity = float(abs(bank(noise, taps, stationary, 'pre')-bank(noise, taps, stationary, 'post')).max())
    difference = float(abs(np.asarray(results['pre'])-results['post']).max())
    assert identity < 1e-12 and difference > .01
    return dict(taps=[v.tolist() for v in taps], observers=[v.tolist() for v in observers],
                gains=gains.tolist(), powers=results, enumeration_error=maximum,
                constant_gain_identity_error=identity, nonconstant_power_difference=difference)
