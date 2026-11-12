"""Euclidean projection of each bounded positive relative-amplitude cone."""
import numpy as np


def project(values, bound, caps):
    values = np.asarray(values, dtype=float)
    caps = np.broadcast_to(caps, (len(values),))
    low, high = 1-bound, 1+bound
    if values.ndim != 2 or not 0 < bound < 1 or np.any(caps <= 0):
        raise ValueError('Invalid amplitude-cone geometry')
    v = values[:, 1:]
    # f'(t) is continuous piecewise affine, with breakpoints v_j/l and v_j/u.
    points = np.sort(np.clip(np.column_stack((np.zeros(len(values)), caps,
        v/low, v/high)), 0, caps[:, None]), axis=1)
    t = points[:, :, None]
    # Below l*t contributes l*(l*t-v), above u*t contributes u*(u*t-v).
    derivative = points-values[:, 0, None] + np.sum(
        low*np.maximum(low*t-v[:, None, :], 0)
        +high*np.minimum(high*t-v[:, None, :], 0), axis=2)
    index = np.argmax(derivative >= 0, axis=1)
    no_root = ~np.any(derivative >= 0, axis=1)
    rows = np.arange(len(values))
    left = points[rows, np.maximum(index-1, 0)]
    right = points[rows, index]
    middle = (left+right)/2
    scale = np.where(v < low*middle[:, None], low,
        np.where(v > high*middle[:, None], high, 0))
    answer = (values[:, 0]+np.sum(scale*v, axis=1))/(1+np.sum(scale**2, axis=1))
    answer = np.clip(answer, left, right)
    answer = np.where(no_root, caps, answer)
    return np.column_stack((answer, np.clip(v, low*answer[:, None], high*answer[:, None])))


def violation(values, bound, caps):
    c0 = values[:, 0]
    return float(max(0, -c0.min(), np.max(c0-caps),
        np.max((1-bound)*c0[:, None]-values[:, 1:]),
        np.max(values[:, 1:]-(1+bound)*c0[:, None])))
