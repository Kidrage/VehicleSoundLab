"""Clamped spline controls with a fixed initial phase/envelope gauge."""
import numpy as np
from scipy.interpolate import BSpline


def spline(time,cycles,spacing):
    knots=np.r_[[0.]*4,np.arange(spacing,cycles,spacing),[float(cycles)]*4]
    full=BSpline.design_matrix(time,knots,3).toarray()
    # The first control is fixed at0. All remaining clamped basis functions
    # vanish at the first sample, removing a common phase/coefficient gauge.
    return full[:,1:]
