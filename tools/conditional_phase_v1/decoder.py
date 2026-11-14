"""Continuous conditional inverse CDF; no oscillator, room or driver ownership."""
import numpy as np
from .transport import hats


def prepare(coupling, row_mass, column_mass, floor):
    # Only an explicit, fixed diagnostic positivity floor. It does not remove
    # high slopes and is not an accepted timbre or temporal process.
    joint = (1-floor)*coupling+floor*row_mass[:, None]*column_mass[None, :]
    conditional = joint/row_mass[:, None]
    return joint, np.column_stack([np.zeros(len(row_mass)), np.cumsum(conditional, axis=1)])


def decode(product, uniform, knots, cdf, low, high):
    weights = hats(product, knots)
    cumulative = weights@cdf
    # Clamp only one-ULP arithmetic at endpoints, not tiny cell probabilities.
    cumulative[:, 0] = 0
    cumulative[:, -1] = 1
    cell = np.sum(uniform[:, None] >= cumulative[:, 1:], axis=1)
    cell = np.minimum(cell, len(low)-1)
    start = cumulative[np.arange(len(cell)), cell]
    probability = cumulative[np.arange(len(cell)), cell+1]-start
    fraction = (uniform-start)/probability
    return low[cell]+fraction*(high[cell]-low[cell])
