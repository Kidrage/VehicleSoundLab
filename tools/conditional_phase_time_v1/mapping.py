"""Same conditional inverse CDF, using only the two nonzero P-hat rows."""
import numpy as np


def decode(product, uniform, knots, cdf, low, high):
    if len(knots) == 1:
        cumulative = np.broadcast_to(cdf[0], (len(product), cdf.shape[1])).copy()
    else:
        left = np.clip(np.searchsorted(knots, product, side='right')-1, 0, len(knots)-2)
        amount = np.clip((product-knots[left])/(knots[left+1]-knots[left]), 0, 1)
        cumulative = (1-amount[:, None])*cdf[left]+amount[:, None]*cdf[left+1]
    cumulative[:, 0] = 0
    cumulative[:, -1] = 1
    cell = np.minimum(np.sum(uniform[:, None] >= cumulative[:, 1:], axis=1), len(low)-1)
    index = np.arange(len(product))
    start = cumulative[index, cell]
    probability = cumulative[index, cell+1]-start
    fraction = (uniform-start)/probability
    return low[cell]+fraction*(high[cell]-low[cell])
