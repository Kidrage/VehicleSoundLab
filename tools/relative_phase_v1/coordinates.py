"""Symmetric stereo phase coordinates; observation L/R are not source objects."""
import numpy as np


def unwrap_gap(phase):
    """Choose a continuous marginal branch at the largest unobserved gap."""
    result = np.empty_like(phase)
    cuts = np.empty(phase.shape[1])
    for j in range(phase.shape[1]):
        values = np.sort(phase[:, j])
        gaps = np.diff(np.r_[values, values[0] + 2*np.pi])
        at = int(np.argmax(gaps))
        cuts[j] = values[at] + gaps[at]/2
        result[:, j] = cuts[j] + np.mod(phase[:, j]-cuts[j], 2*np.pi)
    return result, cuts


def encode(z):
    relative, relative_cut = unwrap_gap(np.angle(z[..., 0]*z[..., 1].conj()))
    common, common_cut = unwrap_gap(np.angle(z[..., 0]*np.exp(-.5j*relative)))
    return np.column_stack([common, relative]), np.r_[common_cut, relative_cut]


def phases(values):
    h = values.shape[-1]//2
    common, relative = values[..., :h], values[..., h:]
    return np.stack([common+.5*relative, common-.5*relative], axis=-1)


def decode(model, normal):
    from radial_copula_v1.quantiles import lookup
    h = len(model['fixed_phase'])
    amplitude = lookup(model['amplitude'], normal[..., :2*h])
    coordinates = lookup(model['phase'], normal[..., 2*h:])
    return amplitude.reshape(normal.shape[:-1]+(h, 2)), phases(coordinates)
