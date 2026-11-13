"""Exact squared common-phase jerk quadrature, retaining original spline space."""
import numpy as np
from scipy.interpolate import BSpline


def build(plan, model, initial_outer):
    cycles, spacing = plan['cycles'], plan['phase_knot_cycles']
    intervals = np.r_[0., np.arange(spacing, cycles, spacing), float(cycles)]
    knots = np.r_[[0.]*6, intervals[1:-1], [float(cycles)]*6]
    spline = BSpline(knots, np.eye(len(knots)-6), 5)
    nodes, weights = np.polynomial.legendre.leggauss(3)
    widths = np.diff(intervals)
    points = ((intervals[:-1]+intervals[1:])[:, None]/2+widths[:, None]*nodes/2).ravel()
    quadrature = (widths[:, None]*weights/2).ravel()
    derivative = spline.derivative(3)(points)[:, 1:]*np.sqrt(quadrature)[:, None]
    assert derivative.shape[1] == model.original.phase_count
    matrix = np.zeros((len(points), model.outer_count))
    first = model.parts
    matrix[:, first:first+model.original.phase_count] = derivative
    initial_norm = float(np.linalg.norm(matrix@initial_outer))
    # Objective units only; a positive global scale does not change the
    # constrained minimum. There is no data-vs-prior penalty weight.
    normalization = initial_norm if initial_norm > np.finfo(float).eps else 1.
    return matrix/normalization, dict(derivative_order=3, gauss_points_per_interval=3,
        exact_polynomial_product_degree=4, objective_normalization=normalization,
        common_phase_dimension=model.original.phase_count, nonphase_columns_zero=True,
        fixed_lowpass_cutoff=False, regularization_weight_selected=False,
        truth_used=False, heldout_used=False)


def controls():
    knots = np.r_[[0.]*6, [.5, 1., 1.5], [2.]*6]
    spline = BSpline(knots, np.eye(len(knots)-6), 5)
    greville = np.array([knots[i+1:i+6].mean() for i in range(len(knots)-6)])
    points = np.linspace(0, 2, 31)
    assert abs(spline.derivative(3)(points)@np.ones(len(greville))).max() < 1e-10
    assert abs(spline.derivative(3)(points)@greville).max() < 1e-10
    # Use independently solved polynomial coefficients only in controls.
    square = np.linalg.lstsq(spline(points), points**2, rcond=None)[0]
    cube = np.linalg.lstsq(spline(points), points**3, rcond=None)[0]
    assert abs(spline.derivative(3)(points)@square).max() < 1e-9
    assert abs(spline.derivative(3)(points)@cube-6).max() < 1e-9
    nodes, weights = np.polynomial.legendre.leggauss(3)
    intervals = np.array([0., .5, 1., 1.5, 2.])
    locations = ((intervals[:-1]+intervals[1:])[:, None]/2+np.diff(intervals)[:, None]*nodes/2).ravel()
    measure = (np.diff(intervals)[:, None]*weights/2).ravel()
    energy = float(np.sum((spline.derivative(3)(locations)@cube)**2*measure))
    assert abs(energy-72) < 1e-8
    return dict(passed=True, affine_and_quadratic_nullspace=True, cubic_exact_jerk_energy=energy)
