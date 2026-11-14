"""Record the original factorization arithmetic and alternative audit projection.

This replay is explicitly NOT an independent SVD implementation. Its actual
residual is checked separately by integer moment arithmetic in ratio_exact.
"""
import numpy as np
from sound_dna.statistics import factorize


def trace(rows, harmonics, components):
    values = np.asarray(rows)
    model, statistics = factorize(values, harmonics, components)
    mean = values.mean(axis=0)
    centered = values-mean
    u, s, v = np.linalg.svd(centered, full_matrices=False)
    k = statistics['components']
    basis = v[:k]*(s[:k, None]/np.sqrt(len(values)-1))
    scores = u[:, :k]*np.sqrt(len(values)-1)
    assert np.array_equal(basis.reshape(k, harmonics, 4).transpose(1, 0, 2), model['basis'])
    actual = (centered-scores@basis).reshape(-1, harmonics, 4)
    flat = model['basis'].transpose(1, 0, 2).reshape(k, harmonics*4)
    alternative_scores = (centered@flat.T)/np.sum(flat*flat, axis=1)[None, :] if k else np.empty((len(values), 0))
    alternative = (centered-alternative_scores@flat).reshape(-1, harmonics, 4)
    return model, statistics, actual, alternative
