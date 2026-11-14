"""Native finite joint moments of powers of stationary multivariate lognormal gains."""
import numpy as np


def finite_moments(gamma, tau, frames_per_block, blocks=8, sample_rate=48000):
    G = np.asarray(gamma, dtype=float)
    if G.ndim != 2 or G.shape[0] != G.shape[1] or not np.all(np.isfinite(G)):
        raise ValueError('Finite square gain covariance required')
    if not np.allclose(G, G.T, rtol=0, atol=1e-13) or np.min(np.diag(G)) < 0:
        raise ValueError('Symmetric covariance with nonnegative diagonal required')
    if np.linalg.eigvalsh(G).min() < -1e-12 * max(1., abs(G).max()):
        raise ValueError('Positive semidefinite gain covariance required')
    if not np.isfinite(tau) or tau <= 0 or not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError('Positive finite time scale and sample rate required')
    if not isinstance(frames_per_block, (int, np.integer)) or frames_per_block < 1:
        raise ValueError('Positive integer block length required')
    if not isinstance(blocks, (int, np.integer)) or blocks < 1:
        raise ValueError('Positive integer block count required')
    channels = len(G)
    coordinate = np.tile(np.arange(channels), 2)
    powers = np.repeat([2., 4.], channels)
    mean = np.exp((powers**2 / 2 - powers) * np.diag(G)[coordinate])
    exponent = powers[:, None] * powers[None, :] * G[np.ix_(coordinate, coordinate)]
    length = frames_per_block * blocks
    rho = np.exp(-np.arange(length) / (sample_rate * tau))
    offset = np.arange(1-frames_per_block, frames_per_block)
    triangle = frames_per_block - abs(offset)
    lags = np.zeros((blocks, len(mean), len(mean)))
    for i in range(len(mean)):
        for j in range(i+1):
            covariance = mean[i] * mean[j] * np.expm1(exponent[i, j] * rho)
            for block in range(blocks):
                if block == 0:
                    value = frames_per_block * covariance[0]
                    value += 2 * np.dot(np.arange(frames_per_block-1, 0, -1), covariance[1:frames_per_block])
                else:
                    value = triangle @ covariance[block*frames_per_block+offset]
                lags[block, i, j] = lags[block, j, i] = value / frames_per_block**2
    full = np.block([[lags[abs(b-a)] for b in range(blocks)] for a in range(blocks)])
    run = np.einsum('a,aij->ij', np.r_[blocks, 2*np.arange(blocks-1, 0, -1)], lags) / blocks**2
    return dict(mean=mean, powers=powers, coordinate=coordinate, gamma=G,
                block_lag_covariance=lags, full_block_covariance=full,
                continuous_run_covariance=run, independent3_run_mean_covariance=run/3)


def observed(gain, frames_per_block, blocks=8):
    g = np.asarray(gain)
    if g.ndim != 2 or len(g) != frames_per_block * blocks:
        raise ValueError('Complete continuous gain path required')
    values = np.concatenate([g**2, g**4], axis=1)
    block = values.reshape(blocks, frames_per_block, values.shape[1]).mean(axis=1)
    return dict(block=block, run=block.mean(axis=0))
