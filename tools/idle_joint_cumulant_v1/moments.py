"""Fourth-order cross-band observation, separate from source/runtime decisions."""
import numpy as np


def joint(x, weights=None):
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError('Expected finite sample-by-band matrix')
    weights = np.ones(len(x)) / len(x) if weights is None else np.asarray(weights, dtype=float)
    if weights.shape != (len(x),) or np.any(weights < 0) or not np.isclose(weights.sum(), 1):
        raise ValueError('Expected normalized nonnegative weights')
    mean = weights @ x
    centered = x - mean
    covariance = centered.T @ (weights[:, None] * centered)
    variance = covariance.diagonal()
    if np.any(variance <= 0):
        raise ValueError('Positive variance required')
    square = centered * centered
    cumulant = square.T @ (weights[:, None] * square) - np.outer(variance, variance) - 2 * covariance**2
    return dict(mean=mean.tolist(), covariance=covariance.tolist(), variance=variance.tolist(),
        cumulant=cumulant.tolist(), normalized=(cumulant / np.outer(variance, variance)).tolist())


def local_normalize(x, frames):
    if len(x) % frames:
        raise ValueError('Whole declared normalization blocks required')
    blocks = np.asarray(x).reshape(-1, frames, x.shape[1])
    rms = np.sqrt(np.mean(blocks**2, axis=1))
    if np.any(rms <= 0):
        raise ValueError('Undefined local RMS; no floor or fill')
    return (blocks / rms[:, None, :]).reshape(x.shape)


def independent_expectation(responses, kappa):
    squares = np.asarray(responses)**2
    return np.einsum('bin,cin,i->bc', squares, squares, kappa)
