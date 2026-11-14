"""Balanced exact AM/PM coefficient populations, independent of audio extraction."""
import numpy as np


def rows(config, name):
    n, h = config['rows'], config['harmonics']
    am = np.resize(config['AM_sign'], n) if name in ('AM_only', 'AM_PM') else np.zeros(n)
    pm = np.resize(config['PM_sign'], n) if name in ('PM_only', 'AM_PM') else np.zeros(n)
    z = np.zeros((n, h, 2), complex)
    for j, order in enumerate(config['orders']):
        for c in (0, 1):
            amplitude = config['amplitudes_L'][j]*(config['right_amplitude_ratio'] if c else 1)
            phase = config['base_phase_L'][j]+c*config['right_phase_offset']
            z[:, order-1, c] = amplitude*(1+config['AM_depth']*am)*np.exp(1j*(phase+config['PM_radians']*pm))
    return np.stack([z.real, z.imag], axis=-1).reshape(n, h*4)


def counterfactuals(a):
    z = a.reshape(len(a), -1, 2, 2)
    z = z[..., 0]+1j*z[..., 1]
    magnitude = abs(z)
    unit = np.divide(z, magnitude, out=np.ones_like(z), where=magnitude > 0)
    mean = z.mean(axis=0)
    fixed = np.divide(mean, abs(mean), out=np.ones_like(mean), where=abs(mean) > 1e-15)
    variants = dict(full=z, phase_only=np.sqrt(np.mean(magnitude**2, axis=0))*unit,
                    amplitude_only=magnitude*fixed)
    return {name: np.stack([v.real, v.imag], axis=-1).reshape(len(a), -1) for name, v in variants.items()}
