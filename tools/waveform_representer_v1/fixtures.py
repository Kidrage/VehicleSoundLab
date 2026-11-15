"""Explicit algebra/finite-frame controls, independent of recordings."""
import numpy as np


def algebra_fixtures():
    rng = np.random.default_rng(758934)
    for label, m, n, channels in (('wide', 5, 8, 1), ('tall', 9, 4, 1),
            ('rank_deficient', 6, 8, 1), ('zero', 5, 8, 1),
            ('disparate', 7, 9, 1), ('two_RHS', 6, 8, 2), ('silent_right', 6, 8, 2)):
        Phi = rng.normal(size=(m, n))
        if label == 'rank_deficient':
            Phi[:, -3:] = Phi[:, :3]
            Phi[-1] = Phi[0]
        if label == 'disparate':
            Phi *= np.geomspace(1., 1e-7, n)[None]
        M = rng.normal(size=(m, m))
        P = rng.normal(size=(n, n))
        W, R = M@M.T+np.eye(m), .001*(P@P.T)+.000001*np.eye(n)
        y = rng.normal(size=(m, channels))
        if label == 'zero': y[:] = 0
        if label == 'silent_right': y[:, 1] = 0
        yield label, Phi, W, R, y


def frame_fixtures():
    size, hop, frames = 16, 4, 41
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    starts = np.arange(-(size-hop), frames, hop)
    coverage = np.zeros(frames)
    for start in starts:
        first, last = max(0, start), min(frames, start+size)
        coverage[first:last] += window[first-start:last-start]**2
    supported = starts[(starts >= 0)&(starts+size <= frames)]
    for label, weights in (('unit', np.ones(9)), ('DC', np.r_[7., np.ones(8)]),
            ('Nyquist', np.r_[np.ones(8), 11.]), ('mixed', np.geomspace(.25, 8., 9))):
        yield label, frames, supported, window, coverage, np.sqrt(frames/(hop*len(supported))), weights, .3
