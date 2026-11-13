"""Scale invariants and frozen-stage derivatives, independent of the known phase."""
import numpy as np
from complex_radial_v1.loss import cost, gradient, quadratic
from .scale import choose


def controls():
    floor = .0002
    cases = [('zero', np.zeros(8), floor), ('below', np.full(8, floor/10), floor),
        ('equal', np.r_[np.full(4, floor), np.zeros(4)], floor),
        ('median', np.r_[np.array([1., 2., 5., 9.]), np.zeros(4)], 3.5)]
    for _, r, expected in cases: assert choose(r, floor)[0] == expected
    r = np.array([.001, -.003, .0002, .0005, -.0015, .002, -.0004, .0001])
    n = len(r)//2; s, median = choose(r, floor)
    c, t = np.cos(.37), np.sin(.37)
    rotated = np.r_[c*r[:n]-t*r[n:], t*r[:n]+c*r[n:]]
    assert abs(choose(rotated, floor)[0]-s) < 1e-12
    index = np.array([2, 0, 3, 1]); permuted = np.r_[r[:n][index], r[n:][index]]
    assert choose(permuted, floor) == (s, median)
    duplicated = np.r_[np.repeat(r[:n], 2), np.repeat(r[n:], 2)]
    assert choose(duplicated, floor) == (s, median)
    assert abs(choose(3*r, 3*floor)[0]-3*s) < 1e-12
    rng = np.random.default_rng(718341); matrix = rng.normal(size=(len(r), 3))
    direction = np.array([.2, -.3, .4]); step = 1e-8
    measured = (cost(r+step*(matrix@direction), s)-cost(r-step*(matrix@direction), s))/(2*step)
    expected = float(direction@(matrix.T@gradient(r, s)))
    derivative_error = abs(measured-expected)/abs(expected); assert derivative_error < 1e-6
    gram, g, weighted, rhs = quadratic(r, matrix[:, :1], s)
    minimizer = float(-g[0]/gram[0, 0])
    assert abs(float(weighted[:, 0]@rhs/(weighted[:, 0]@weighted[:, 0]))-minimizer) < 1e-12
    invalid = 0
    for bad, bad_floor in ((np.zeros(0), floor), (np.zeros(3), floor),
            (np.full(4, np.nan), floor), (np.zeros(4), 0.)):
        try: choose(bad, bad_floor)
        except ValueError: invalid += 1
        else: raise AssertionError('Invalid scale input accepted')
    return dict(passed=True, zero_floor_equality_median=True, fixed_rotation_permutation_duplicate_gain=True,
        frozen_stage_derivative_relative_error=float(derivative_error), scalar_quadratic_minimizer=minimizer,
        invalid_inputs_rejected=invalid)
