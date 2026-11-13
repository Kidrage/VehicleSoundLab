"""Reconstruct every saved original box-QP certificate and trust decision, without solves."""
import math
import numpy as np


def certificate(design, rhs, lower, upper, qp, published, settings, scalar=False):
    x, y, z = (np.asarray(qp[key]) for key in ('primal_solution', 'dual_solution', 'inequality_dual'))
    assert len(z) == 2*len(x) and np.array_equal(y, z[:len(x)]-z[len(x):])
    gram, gradient = design.T@design, -design.T@rhs
    maximum = float(abs(gradient).max())
    scale = maximum if maximum > 0 else max(float(abs(gram).max()), 1.)
    assert scale == qp['objective_scale']
    residual = design@x-rhs
    slack = np.r_[upper-x, x-lower]
    measures = dict(primal=float(max(0., (lower-x).max(), (x-upper).max())),
        gram_stationarity=float(abs(((gram+gram.T)/(2*scale))@x+gradient/scale+y).max()),
        raw_sample_stationarity=float(abs(design.T@residual/scale+y).max()),
        dual_sign=float(max(0., -z.min())), complementarity=float(abs(z*slack).max()),
        quadratic_objective=float(.5*x@gram@x+gradient@x),
        raw_least_squares_objective=float(.5*(residual@residual)))
    measures['raw_quadratic_objective_closure'] = abs(measures['raw_least_squares_objective']-
        (measures['quadratic_objective']+.5*(rhs@rhs)))
    error = max(abs(value-published[key]) for key, value in measures.items())
    assert error <= 1e-12 and measures['quadratic_objective'] == qp['objective']
    passed = bool(measures['primal'] <= settings['maximum_primal_violation'] and
        max(measures['gram_stationarity'], measures['raw_sample_stationarity']) <= settings['maximum_normalized_stationarity'] and
        measures['dual_sign'] <= settings['maximum_primal_violation'] and
        measures['complementarity'] <= settings['maximum_complementarity'] and
        measures['raw_quadratic_objective_closure'] <= 1e-12)
    assert passed == published['success']
    if scalar:
        vector = np.array([math.fsum(float(a*b) for a, b in zip(column, residual))
                           for column in design.T])/scale+y
        measures['scalar_stationarity'] = float(abs(vector).max())
        measures['scalar_gradient_error'] = float(abs(vector-(design.T@residual/scale+y)).max())
        assert measures['scalar_stationarity'] <= settings['maximum_normalized_stationarity']
    return dict(passed=passed, maximum_published_error=error, measurements=measures)


def trace(model, target, initial, published, settings, independent_model=None):
    x = initial.copy()
    _, jacobian = model.samples(x, True)
    scales = np.minimum(1/np.maximum(np.linalg.norm(jacobian, axis=0), 1e-30), (model.upper-model.lower)/2)
    assert np.array_equal(scales, np.asarray(published['scales']))
    radius = settings['initial_radius']
    assert float(.5*np.sum((model.samples(x)-target)**2)) == published['initial_cost']
    rows = []
    independent_derivative_error = 0.
    for index, row in enumerate(published['history']):
        assert row['iteration'] == index+1 and row['radius'] == radius
        values, derivative = model.samples(x, True)
        if independent_model:
            other_value, other_derivative = independent_model(x)
            assert abs(other_value-values).max() <= 1e-12
            error = float(abs(other_derivative-derivative).max())
            independent_derivative_error = max(independent_derivative_error, error)
            assert error <= 1e-12
        design = derivative*scales[None, :]
        residual = values-target
        lower, upper = np.maximum((model.lower-x)/scales, -radius), np.minimum((model.upper-x)/scales, radius)
        result = row['subproblem']
        qp = result['qp']
        audit = certificate(design, -residual, lower, upper, qp, result['certificate'], settings,
                            scalar=index in (0, len(published['history'])-1))
        if qp['primal_polish_attempted']:
            coarse = certificate(design, -residual, lower, upper, qp['coarse_attempt'],
                                 result['coarse_certificate'], settings)
            assert not coarse['passed']
        else:
            assert result['coarse_certificate'] == result['certificate']
        step = np.asarray(qp['primal_solution'])
        candidate = x+scales*step
        assert np.array_equal(candidate, np.asarray(row['candidate_parameters']))
        violation = float(max(0., (model.lower-candidate).max(), (candidate-model.upper).max()))
        before = float(.5*(residual@residual))
        next_residual = model.samples(candidate)-target
        cost = float(.5*(next_residual@next_residual))
        predicted, actual = -qp['objective'], before-cost
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(audit['passed'] and violation <= settings['maximum_primal_violation'] and
            predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
        expected = dict(before_cost=before, candidate_cost=cost, predicted_reduction=predicted,
            actual_reduction=actual, ratio=ratio, accepted=accepted,
            original_parameter_violation=violation, scaled_step_maximum=float(abs(step).max()))
        assert all(value == row[key] for key, value in expected.items())
        rows.append(dict(iteration=index+1, accepted=accepted, certificate=audit))
        if not audit['passed']:
            assert index == len(published['history'])-1
            break
        if accepted:
            x = candidate
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(step).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        if radius < settings['minimum_radius']:
            assert index == len(published['history'])-1
            break
    assert radius == published['final_radius']
    assert float(.5*np.sum((model.samples(x)-target)**2)) == published['final_cost']
    assert len(rows) == published['iterations'] and sum(row['accepted'] for row in rows) == published['accepted_steps']
    assert all(row['certificate']['passed'] for row in rows) == published['every_subproblem_certified']
    return x, dict(rows=rows, all_candidates_costs_decisions_and_radii_exact=True,
        maximum_independent_derivative_error=independent_derivative_error, large_QPs_rerun=False)
