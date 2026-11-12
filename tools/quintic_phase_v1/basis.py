"""Clamped degree-five common phase, preserving the initial zero gauge."""
import numpy as np
from scipy.interpolate import BSpline


def basis(time, cycles, spacing):
    knots = np.r_[[0.]*6, np.arange(spacing, cycles, spacing), [float(cycles)]*6]
    full = BSpline.design_matrix(time, knots, 5).toarray()
    if full.min() < -1e-12 or abs(full.sum(axis=1)-1).max() > 1e-12:
        raise ValueError('Quintic phase partition invalid')
    reduced = full[:, 1:]
    if time[0] == 0 and abs(reduced[0]).max() != 0:
        raise ValueError('Initial common-phase gauge changed')
    return reduced
