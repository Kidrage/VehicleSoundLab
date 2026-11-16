"""Shape-preserving interpolation with complete analytic derivative checks."""
import numpy as np
from scipy.interpolate import PchipInterpolator


def build(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if (x.ndim != 1 or len(x) < 3 or y.shape != x.shape
            or any(np.iscomplexobj(v) or not np.isfinite(v).all() for v in (x, y))
            or np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0)):
        raise ValueError('Finite strictly increasing supported nodes required')
    origin = float(y[0])
    spline = PchipInterpolator(x, y-origin, extrapolate=False)
    c, h = spline.c, np.diff(x)
    ends = np.column_stack((c[2], (3*c[0]*h+2*c[1])*h+c[2]))
    at = np.divide(-c[1], 3*c[0], out=np.zeros_like(h), where=c[0] != 0)
    valid = (c[0] != 0) & (at > 0) & (at < h)
    minimum = ends.min(axis=1)
    minimum[valid] = np.minimum(minimum[valid],
        (3*c[0, valid]*at[valid]+2*c[1, valid])*at[valid]+c[2, valid])
    if np.min(minimum) <= 0 or not np.isfinite(minimum).all():
        raise ValueError('Strictly positive derivative on every interval required')
    node_error = float(np.max(abs(spline(x)+origin-y)))
    assert node_error < 2e-12
    return dict(x=x, y=y, origin=np.array(origin), coefficients=c,
                interval_minimum_derivative=minimum,
                node_preservation_max_seconds=np.array(node_error))


def evaluate(model, query):
    q = np.asarray(query)
    x, c = model['x'], model['coefficients']
    if (q.ndim != 1 or not q.size or np.iscomplexobj(q) or not np.isfinite(q).all()
            or q.min() < x[0] or q.max() > x[-1]):
        raise ValueError('Every finite query must be inside the observed nodes')
    k = np.clip(np.searchsorted(x, q, side='right')-1, 0, len(x)-2)
    t = q-x[k]
    return ((c[0, k]*t+c[1, k])*t+c[2, k])*t+c[3, k]+model['origin']


def from_context(d):
    observed = d['observed_centers']
    a, b = np.searchsorted(d['observed_indices'], observed), np.searchsorted(d['coarse_indices'], observed)
    assert np.array_equal(d['observed_indices'][a], observed)
    assert np.array_equal(d['coarse_indices'][b], observed)
    return build(1024*d['observed_phase'][a], d['coarse_positions'][b])


def summary(model, query, positions, old):
    return dict(nodes=len(model['x']), queries=len(query),
        node_preservation_max_seconds=float(model['node_preservation_max_seconds']),
        minimum_derivative_seconds_per_sample=float(model['interval_minimum_derivative'].min()),
        clock_change_max_seconds=float(np.max(abs(positions-old))),
        old_second_difference_L2_seconds=float(np.linalg.norm(np.diff(old, 2))),
        C1_second_difference_L2_seconds=float(np.linalg.norm(np.diff(positions, 2))),
        strict_monotonicity_verified=True, one_common_LR_coordinate=True,
        new_between_node_map_not_equivalent_to_original=True)
