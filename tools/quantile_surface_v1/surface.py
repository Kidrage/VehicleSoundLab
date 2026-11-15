"""Blend conditional row quantiles: a NEW phase law, not a CDF fast path.

For fixed u the P derivative inside a knot interval is exactly the difference
of its two row quantiles divided by the knot width. No tiny probability occurs
in that derivative. Row inverse probabilities still affect the u derivative.
All rows must share the same declared phase branch and cell support.
"""
import numpy as np


def row_inverse(uniform, cumulative, low, high):
    cell = np.minimum(np.searchsorted(cumulative[1:], uniform, side='right'), len(low)-1)
    mass = cumulative[cell+1]-cumulative[cell]
    if np.any(mass <= 0):
        raise ValueError('Selected cell has no probability')
    return low[cell]+(uniform-cumulative[cell])/mass*(high[cell]-low[cell])


def evaluate(product, uniform, knots, cumulative, low, high):
    """Same row inverse at every P knot, linear quantile blend BETWEEN knots."""
    product, uniform = np.broadcast_arrays(product, uniform)
    if len(knots) == 1:
        return row_inverse(uniform, cumulative[0], low, high)
    left = np.clip(np.searchsorted(knots, product, side='right')-1, 0, len(knots)-2)
    weight = np.clip((product-knots[left])/(knots[left+1]-knots[left]), 0, 1)
    result = np.empty_like(uniform, dtype=float)
    for node in np.unique(left):
        selected = left == node
        a = row_inverse(uniform[selected], cumulative[node], low, high)
        b = row_inverse(uniform[selected], cumulative[node+1], low, high)
        result[selected] = a+weight[selected]*(b-a)
    return result
