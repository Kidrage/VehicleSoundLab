"""Finite oscillator comparison. Coefficient statistics, never recorded trajectories."""
import numpy as np
from scipy import signal
from .kernel import interpolation


def white_nodes(kernel, seed, seconds, dimensions):
    h = np.array(kernel, dtype=float, copy=True)
    h /= np.linalg.norm(h)
    count = int(np.ceil(seconds * 500)) + 4
    warm = len(h) - 1
    rng = np.random.Generator(np.random.PCG64(seed ^ 0x682D7439A851))
    white = rng.standard_normal((count + warm, dimensions))
    # Filter independent streams before the coefficient factor. Full prehistory.
    filtered = signal.fftconvolve(white, h[:, None], axes=0)[warm:warm+count]
    return filtered, white


def render(model, phase, q, profile, white, block=1920):
    harmonics = model['harmonics']
    groups = model['groups']
    m = len(harmonics)
    frames = len(phase)
    _, weights, _ = interpolation(model['node_kernel'])
    # Both factors use the SAME independent Gaussian coordinates and interpolation.
    nodes = {name: white @ model[name + '_factor'].T
             for name in ['independent', 'joint']}
    out = {name: np.zeros((frames, 2)) for name in nodes}
    for start in range(0, frames, block):
        stop = min(frames, start + block)
        index = np.arange(start, stop)
        node_index, fraction = np.divmod(index, 96)
        w = weights[fraction]
        angle = phase[start:stop, None] * harmonics
        cosine, sine = np.cos(angle), np.sin(angle)
        for name, data in nodes.items():
            coefficient = sum(w[:, k, None] * data[node_index+k] for k in range(4))
            oscillator = coefficient[:, :m]*cosine - coefficient[:, m:]*sine
            for band in range(4):
                y = oscillator[:, groups == band].sum(axis=1) * np.sqrt(q[start:stop, band])
                ratio = profile['kernels'][band+2]['right_over_left']
                out[name][start:stop] += y[:, None] * [1., ratio]
    return out, nodes
