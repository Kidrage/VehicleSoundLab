"""Nominal carrier-origin tags; these are not physical engine sources."""
import numpy as np


def indices(harmonics, root, edges):
    hz = np.arange(1, harmonics+1)*root
    result = np.searchsorted(np.asarray(edges), hz, side='right')-1
    assert np.all((result >= 0)&(result < len(edges)-1))
    return result
