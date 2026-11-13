"""Concave-power tangent majorizer of radial soft-L1, not its exact Hessian."""
import numpy as np
from complex_radial_v1.loss import cost, pairs, stacked


def weights(residual, scale):
    r = pairs(residual)
    return 1/np.sqrt(1+np.sum(r*r, axis=1)/scale**2)


def surrogate(residual, proposed, scale):
    v = weights(residual, scale)
    return float(cost(residual, scale)+.5*np.sum(v*(np.sum(pairs(proposed)**2, axis=1)-np.sum(pairs(residual)**2, axis=1))))


def quadratic(residual, matrix, scale):
    v = weights(residual, scale); root = np.sqrt(np.r_[v, v])
    weighted = root[:, None]*matrix
    # weighted.T@rhs = -J.T*psi, same original radial objective gradient.
    rhs = -root*residual
    return weighted.T@weighted, matrix.T@(np.r_[v, v]*residual), weighted, rhs
