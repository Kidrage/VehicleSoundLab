"""Safeguarded normalized-cubic Newton solve at every source-time query."""
import numpy as np
from clock_c1_v1.geometry import evaluate


def invert(model, seconds):
    t = np.asarray(seconds)
    x, y, c = model['x'], model['y'], model['coefficients']
    if (t.ndim != 1 or not t.size or np.iscomplexobj(t) or not np.isfinite(t).all()
            or t.min() < y[0] or t.max() > y[-1]):
        raise ValueError('Every finite inverse query needs observed clock support')
    k = np.clip(np.searchsorted(y, t, side='right')-1, 0, len(y)-2)
    h = x[k+1]-x[k]
    a, b, v = c[0, k]*h**3, c[1, k]*h**2, c[2, k]*h
    target = t-y[k]
    s = target/(y[k+1]-y[k]); low = np.zeros(len(t)); high = np.ones(len(t))
    for _ in range(12):
        f = ((a*s+b)*s+v)*s-target
        low = np.where(f < 0, s, low); high = np.where(f > 0, s, high)
        proposal = s-f/((3*a*s+2*b)*s+v)
        bad = (proposal < low) | (proposal > high) | ~np.isfinite(proposal)
        s = np.where(bad, (low+high)/2, proposal)
    result = x[k]+h*s
    closure = float(np.max(abs(evaluate(model, result)-t)))
    if closure > 2e-12:
        raise ValueError('Cubic inverse failed the original source-time closure gate')
    return result


def roundtrip(model, query):
    times = evaluate(model, query)
    back = invert(model, times)
    # Convert virtual-coordinate error to seconds by the relevant secant.
    k = np.clip(np.searchsorted(model['x'], query, side='right')-1, 0, len(model['x'])-2)
    slope = np.diff(model['y'])[k]/np.diff(model['x'])[k]
    error = float(np.max(abs(back-query)*slope))
    nodes = invert(model, model['y'])
    node_error = float(np.max(abs(nodes-model['x'])))
    assert error < 2e-12 and node_error/1024 < 2e-11
    return dict(source_grid_roundtrip_max_seconds=error, observed_node_inverse_max_cycles=node_error/1024)
