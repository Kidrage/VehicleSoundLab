"""Independent convex/derivative/equivalence controls before vehicle extraction."""
import numpy as np
from scipy.optimize import minimize, Bounds, LinearConstraint
from .cone import project, violation
from .quadratic import solve
from .amplitude import solve_amplitudes, cost
from .model import AbsoluteModel


def inequalities(groups, controls, bound):
    matrix = np.zeros((2*groups*(controls-1), groups*controls))
    for k in range(groups):
        for j in range(1, controls):
            row = 2*(k*(controls-1)+j-1)
            matrix[row, k*controls] = -(1-bound)
            matrix[row, k*controls+j] = 1
            matrix[row+1, k*controls] = 1+bound
            matrix[row+1, k*controls+j] = -1
    return matrix


def controls(time, plan, variant, settings, original_parameters):
    rng = np.random.default_rng(739102)
    maximum_projection_error = 0.
    for _ in range(8):
        value = rng.normal(.3, 1, (1, 5))
        cap = rng.uniform(.2, 1.4)
        expected = project(value, .25, np.array([cap]))
        upper = np.r_[cap, np.full(4, np.inf)]
        independent = minimize(lambda x: .5*np.sum((x-value.ravel())**2), expected.ravel()*.9,
            jac=lambda x: x-value.ravel(), bounds=Bounds(np.zeros(5), upper),
            constraints=[LinearConstraint(inequalities(1, 5, .25), 0, np.inf)],
            method='SLSQP', options=dict(ftol=1e-13, maxiter=100))
        error = float(abs(expected.ravel()-independent.x).max())
        maximum_projection_error = max(maximum_projection_error, error)
        assert independent.success and error < 1e-7
        assert violation(expected, .25, np.array([cap])) < 1e-12
    groups, count = 3, 3
    design = rng.normal(0, .3, (35, groups*count))
    target = rng.normal(.1, .3, 35)
    caps = np.array([.25, .4, .7])
    initial = np.full((groups, count), .1)
    gram, linear = design.T@design, design.T@target
    result, qp = solve(gram, linear, initial, .25, caps, settings)
    matrix = inequalities(groups, count, .25)
    upper = np.full(groups*count, np.inf)
    upper[::count] = caps
    independent = minimize(lambda x: .5*x@gram@x-linear@x, initial.ravel(),
        jac=lambda x: gram@x-linear, method='SLSQP',
        bounds=Bounds(np.zeros(groups*count), upper), constraints=[LinearConstraint(matrix, 0, np.inf)],
        options=dict(ftol=1e-13, maxiter=200))
    qp_error = float(abs(result.ravel()-independent.x).max())
    assert independent.success and qp['success'] and qp_error < 1e-6
    robust, irls = solve_amplitudes(design, target, initial, .25, caps, .2, settings)
    def gradient(x):
        residual = design@x-target
        return design.T@(residual/np.sqrt(1+(residual/.2)**2))
    independent_robust = minimize(lambda x: cost(design@x-target, .2), initial.ravel(), jac=gradient,
        method='SLSQP', bounds=Bounds(np.zeros(groups*count), upper),
        constraints=[LinearConstraint(matrix, 0, np.inf)], options=dict(ftol=1e-13, maxiter=300))
    robust_error = float(abs(robust.ravel()-independent_robust.x).max())
    assert independent_robust.success and irls['success'] and robust_error < 1e-5
    model = AbsoluteModel(time, plan, variant, [])
    outer, absolute = model.unpack(original_parameters)
    roundtrip = model.pack(outer, absolute)
    equivalent = float(abs(model.original.prediction(roundtrip)-model.original.prediction(original_parameters)).max())
    sample_equal = float(abs(model.prediction(outer, absolute)-model.original.prediction(roundtrip)).max())
    design_equal = float(abs(model.design(outer)@absolute.ravel()-model.prediction(outer, absolute)).max())
    assert max(equivalent, sample_equal, design_equal) < 1e-12
    _, jacobian = model.prediction(outer, absolute, True)
    derivatives = []
    for name, index in [('constant_phase', 2), ('common_phase', model.parts+31)]:
        direction = np.zeros_like(outer)
        direction[index] = 1
        step = 1e-6
        observed = (model.prediction(outer+step*direction, absolute)
            -model.prediction(outer-step*direction, absolute))/(2*step)
        error = float(np.linalg.norm(observed-jacobian[:, index])/np.linalg.norm(jacobian[:, index]))
        assert error < plan['rules']['maximum_jacobian_relative_error']
        derivatives.append(dict(direction=name, relative_error=error))
    # Explicit coefficient-box branch at c0>1, and zero-amplitude round trip.
    angles = outer.copy()
    absolute = absolute.copy()
    angles[0] = np.pi/4
    absolute[0] = 1.2
    lower, upper = model.phase_bounds(absolute, angles)
    assert lower[0] < angles[0] < upper[0]
    for angle in (lower[0], upper[0]):
        assert max(abs(1.2*np.cos(angle)), abs(1.2*np.sin(angle))) <= 1+1e-12
    absolute[1] = 0
    packed = model.pack(angles, absolute)
    assert np.isfinite(packed).all()
    return dict(passed=True, projection_maximum_error=maximum_projection_error,
        qp_independent_maximum_error=qp_error, qp=qp,
        robust_independent_maximum_error=robust_error, robust_projected_kkt=irls['robust_projected_kkt'],
        parameter_roundtrip_projection_error=equivalent, sample_projection_equivalence=sample_equal,
        absolute_design_equivalence=design_equal, derivatives=derivatives,
        coefficient_box_branch_and_zero_checked=True)
