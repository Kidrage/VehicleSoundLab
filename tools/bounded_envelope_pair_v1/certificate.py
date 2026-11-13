"""Full original ranged-polytope KKT, including independent sample-space gradient."""
import numpy as np


def certify(qp, design, rhs, matrix, lower, upper, settings):
    x = np.asarray(qp['primal_solution'])
    y = np.asarray(qp['dual_solution'])
    z = np.asarray(qp['inequality_dual'])
    high = np.flatnonzero(np.isfinite(upper))
    low = np.flatnonzero(np.isfinite(lower))
    mapped = np.zeros(len(lower))
    mapped[high] += z[:len(high)]
    mapped[low] -= z[len(high):]
    assert np.array_equal(mapped, y)
    observed = matrix@x
    primal = float(max(0., (lower-observed).max(), (observed-upper).max()))
    slack = np.r_[upper[high]-observed[high], observed[low]-lower[low]]
    sign = float(max(0., -z.min()))
    complementarity = float(abs(z*slack).max())
    gram = design.T@design
    gradient = -(design.T@rhs)
    maximum = float(abs(gradient).max())
    scale = maximum if maximum > 0 else max(float(abs(gram).max()), 1.)
    assert scale == qp['objective_scale']
    normal_gradient = ((gram+gram.T)/(2*scale))@x+gradient/scale
    gram_stationarity = float(abs(normal_gradient+matrix.T@y).max())
    residual = design@x-rhs
    raw_stationarity = float(abs(design.T@residual/scale+matrix.T@y).max())
    objective = float(.5*x@gram@x+gradient@x)
    assert objective == qp['objective']
    raw_objective = float(.5*(residual@residual))
    closure = abs(raw_objective-(objective+.5*(rhs@rhs)))
    success = bool(primal <= settings['maximum_primal_violation']
        and max(gram_stationarity, raw_stationarity) <= settings['maximum_normalized_stationarity']
        and sign <= settings['maximum_primal_violation']
        and complementarity <= settings['maximum_complementarity'] and closure <= 1e-12)
    return dict(success=success, primal=primal, gram_stationarity=gram_stationarity,
        raw_sample_stationarity=raw_stationarity, dual_sign=sign, complementarity=complementarity,
        quadratic_objective=objective, raw_least_squares_objective=raw_objective,
        raw_quadratic_objective_closure=closure, original_limits_unchanged=True)
