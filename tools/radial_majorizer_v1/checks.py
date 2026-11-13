"""Predeclared exact tangent/bound/rotation and fixed-amplitude controls."""
import numpy as np
from complex_radial_v1.loss import cost, gradient
from .geometry import weights, surrogate, quadratic


def controls():
    s = .0002
    residual = np.array([.001, -.003, .0002, .0005, -.0015, .002, -.0004, .0001])
    proposed = [np.zeros(8), -residual, 2*residual,
        np.array([.004, -.0002, .003, -.001, -.002, .001, .003, -.002])]
    assert weights(np.zeros(8), s).tolist() == [1.]*4
    assert surrogate(residual, residual, s) == cost(residual, s)
    margins = [surrogate(residual, z, s)-cost(z, s) for z in proposed]
    assert min(margins) >= -1e-12
    n = len(residual)//2; c, t = np.cos(.37), np.sin(.37)
    def rotate(x): return np.r_[c*x[:n]-t*x[n:], t*x[:n]+c*x[n:]]
    rotation_error = max(abs(surrogate(rotate(residual), rotate(z), s)-surrogate(residual, z, s)) for z in proposed)
    assert rotation_error <= 1e-12
    matrix = np.arange(24).reshape(8, 3)/19-.5
    gram, g, weighted, rhs = quadratic(residual, matrix, s)
    gradient_error = float(abs(g-matrix.T@gradient(residual, s)).max()); assert gradient_error <= 1e-12
    assert np.linalg.norm(weighted.T@rhs+g) <= 1e-12
    direction = np.array([.2, -.3, .4]); h = 1e-8
    finite = (cost(residual+h*(matrix@direction), s)-cost(residual-h*(matrix@direction), s))/(2*h)
    derivative_error = abs(finite-direction@g)/abs(direction@g); assert derivative_error <= 1e-6
    # Fixed analytic radial scalar: old local Newton overshoots, derived M bounds it.
    scalar = np.array([10*s, 0.]); v = 1/np.sqrt(101.)
    newton = np.array([-10*s/v**2]); z = scalar+np.r_[newton, 0.]
    assert cost(z, s) > cost(scalar, s) and surrogate(scalar, z, s) >= cost(z, s)
    # A fixed, linearly parameterized two-carrier amplitude fixture. No clock fit.
    time = np.arange(64)/64
    basis = np.column_stack((np.cos(2*np.pi*3*time+.2), np.cos(2*np.pi*7*time-.4)))
    target = basis@np.array([.04, .02]); initial = np.array([.03, .025])
    r = np.r_[basis@initial-target, np.zeros(64)]
    design = np.vstack((basis, np.zeros_like(basis)))
    g2, q2, _, _ = quadratic(r, design, s)
    # Unconstrained2x2 SPD linear-amplitude minimizer; no known phase involved.
    step = np.linalg.solve(g2, -q2); new_r = r+design@step
    assert surrogate(r, new_r, s) <= cost(r, s) and cost(new_r, s) <= surrogate(r, new_r, s)+1e-12
    assert abs(initial+step-np.array([.04, .02])).max() < 1e-12
    return dict(passed=True, tangent_equality=True, zero_weights=True, fixed_bound_margins=margins,
        rotation_maximum_error=float(rotation_error), gradient_maximum_error=gradient_error,
        derivative_relative_error=float(derivative_error), fixed_linear_amplitude_exact=True,
        scalar_old_Newton_overshoot=True,
        limit='Residual-space bound is not a nonlinear waveform or physical source guarantee')
