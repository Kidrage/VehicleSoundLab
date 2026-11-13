"""Nested acoustic features; each difference is formed before downsampling."""
import numpy as np

PAIRS = [(0, 1), (0, 2), (1, 2)]


def matrix(phasors, expanded=True, hop=48, trim=12000):
    z = np.asarray(phasors)
    if z.ndim != 2 or z.shape[1] != 3 or not np.isfinite(z).all():
        raise ValueError('Three finite complex phasors required')
    if expanded:
        z = np.column_stack((z, *[z[:, j] * z[:, i].conj() for i, j in PAIRS]))
    # Preserve the parent's real-column summation order for byte-exact native features.
    feature = np.column_stack((z.real, z.imag))
    feature = feature[trim:-trim] if trim else feature
    if len(feature) % hop:
        raise ValueError('No partial observation blocks')
    return feature.reshape(-1, hop, feature.shape[1]).mean(axis=1)
