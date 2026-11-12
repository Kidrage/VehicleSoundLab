"""Independent explicit-polytope checks of joint projections and QPs."""
from copy import deepcopy
import numpy as np
from scipy.optimize import minimize, Bounds, LinearConstraint
from absolute_amplitude_v1.model import AbsoluteModel
from .constraints import Region
from .quadratic import solve


def explicit(model, outer, controls, scales, radius):
    n = len(outer)
    total = n+controls.size
    lower = np.full(total, -radius)
    upper = np.full(total, radius)
    m = model.original
    for k in range(m.parts, n):
        bound = model.phase_bound if k < m.parts+m.phase_count else model.departure_bound
        lower[k] = max(lower[k], (-bound-outer[k])/scales[k])
        upper[k] = min(upper[k], (bound-outer[k])/scales[k])
    rows, lows, highs = [], [], []
    for k in range(model.parts):
        first = n+k*model.controls
        row = np.zeros(total); row[first] = scales[first]
        rows.append(row); lows.append(-controls[k, 0]); highs.append(np.sqrt(2)-controls[k, 0])
        for j in range(1, model.controls):
            for multiplier, sign in ((1-model.bound, 1), (1+model.bound, -1)):
                row = np.zeros(total)
                row[first+j] = sign*scales[first+j]
                row[first] = -sign*multiplier*scales[first]
                rows.append(row); lows.append(sign*(multiplier*controls[k, 0]-controls[k, j])); highs.append(np.inf)
        phi, c0 = outer[k], controls[k, 0]
        for value, dc, dp in ((c0*np.cos(phi), np.cos(phi), -c0*np.sin(phi)),
            (c0*np.sin(phi), np.sin(phi), c0*np.cos(phi))):
            row = np.zeros(total); row[first] = dc*scales[first]; row[k] = dp*scales[k]
            rows.append(row); lows.append(-1-value); highs.append(1-value)
    return Bounds(lower, upper), LinearConstraint(np.asarray(rows), np.asarray(lows), np.asarray(highs))


def controls(base, variant, settings, qp_solver=solve):
    plan = deepcopy(base)
    plan.update(cycles=10, source_orders=[1., 1.2, 1.4], phase_knot_cycles=5.)
    time = np.arange(plan['cycles']*plan['samples_per_cycle'])/plan['samples_per_cycle']
    model = AbsoluteModel(time, plan, variant, [])
    outer = np.r_[[.4, .9, -.7], np.linspace(-.12, .15, model.original.phase_count)]
    absolute = np.array([.1, 1.25, .2])[:, None]*np.ones((3, model.controls))
    absolute[:, 1] *= .75
    absolute[:, 2] *= 1.25
    scales = np.r_[np.full(3, .3), np.full(model.original.phase_count, .05), np.full(absolute.size, .1)]
    rng = np.random.default_rng(602931)
    evidence = []
    for label, radius in (('tight', .25), ('coefficient_box_active', 1.)):
        region = Region(model, outer, absolute, scales, radius, settings)
        bounds, constraints = explicit(model, outer, absolute, scales, radius)
        request = rng.normal(0, 2, len(scales))
        if label == 'coefficient_box_active':
            request[1] = 3
            request[len(outer)+model.controls] = 3
        actual, projection = region.project(request)
        expected = minimize(lambda x: .5*np.sum((x-request)**2), np.zeros(len(scales)),
            jac=lambda x: x-request, method='SLSQP', bounds=bounds, constraints=[constraints],
            options=dict(ftol=1e-13, maxiter=400))
        error = float(abs(actual-expected.x).max())
        assert expected.success and projection['success'] and error < 1e-6
        design = rng.normal(0, .4, (len(scales)+15, len(scales)))
        gram = design.T@design
        gradient = rng.normal(0, .3, len(scales))
        solved, qp = qp_solver(gram, gradient, region, settings)
        independent = minimize(lambda x: .5*x@gram@x+gradient@x, np.zeros(len(scales)),
            jac=lambda x: gram@x+gradient, method='SLSQP', bounds=bounds, constraints=[constraints],
            options=dict(ftol=1e-13, maxiter=400))
        qp_error = float(abs(solved-independent.x).max())
        assert independent.success and qp['success'] and qp_error < 1e-5
        new_outer, new_controls, effective, exact = region.retract(solved)
        assert exact['original_parameter_error'] < 1e-9 and exact['amplitude_cone_error'] < 1e-9
        evidence.append(dict(id=label, projection_maximum_error=error, projection=projection,
            qp_maximum_error=qp_error, qp=qp, retraction=exact,
            nonzero_step_norm=float(np.linalg.norm(solved))))
        assert evidence[-1]['nonzero_step_norm'] > .01
    # The explicit Cartesian coefficient linearization must agree with the
    # differential of the exact nonlinear coefficient function.
    direction = rng.normal(0, .01, len(scales))
    first = len(outer)+model.controls
    phi, c0 = outer[1], absolute[1, 0]
    expected_a = np.cos(phi)*scales[first]*direction[first]-c0*np.sin(phi)*scales[1]*direction[1]
    step = 1e-5
    def a(t):
        return (c0+t*scales[first]*direction[first])*np.cos(phi+t*scales[1]*direction[1])
    error = abs((a(step)-a(-step))/(2*step)-expected_a)/max(abs(expected_a), 1e-30)
    assert error < 1e-6
    return dict(passed=True, cases=evidence, coefficient_linearization_relative_error=float(error),
        limits=['Convex joint controls do not qualify the full engine coordinate or real timbre'])
