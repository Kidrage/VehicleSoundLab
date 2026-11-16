"""Independent normalized PCHIP coefficients and per-query scalar bisection."""
import numpy as np
from clock_c1_v1.audit_geometry import verify as original_geometry


def coefficients(model):
    x, y = map(lambda v:np.asarray(v, np.longdouble), (model['x'], model['y']))
    h, dy = np.diff(x), np.diff(y); d = dy/h
    slopes = np.zeros(len(x), np.longdouble)
    for k in range(1, len(x)-1):
        w1, w2 = 2*h[k]+h[k-1], h[k]+2*h[k-1]
        slopes[k] = (w1+w2)/(w1/d[k-1]+w2/d[k])
    for out, a, b in ((0, 0, 1), (-1, -1, -2)):
        m = ((2*h[a]+h[b])*d[a]-h[a]*d[b])/(h[a]+h[b])
        slopes[out] = 0 if m*d[a] <= 0 else min(m, 3*d[a]) if d[a]*d[b] <= 0 else m
    a = h*slopes[:-1]
    b = 3*dy-h*(2*slopes[:-1]+slopes[1:])
    c = -2*dy+h*(slopes[:-1]+slopes[1:])
    got = model['coefficients']*np.array([h**3, h**2, h, np.ones(len(h))])
    wanted = np.stack((c, b, a, y[:-1]-y[0]))
    assert np.max(abs(got-wanted)) < 2e-12
    return x, y, h, a, b, c


def invert(model, times):
    x, y, h, a, b, c = coefficients(model)
    t = np.asarray(times, np.longdouble)
    assert t.min() >= y[0] and t.max() <= y[-1]
    k = np.clip(np.searchsorted(y, t, side='right')-1, 0, len(y)-2)
    target = t-y[k]
    lo, hi = np.zeros(len(t), np.longdouble), np.ones(len(t), np.longdouble)
    for _ in range(48):
        middle = (lo+hi)/2
        value = a[k]*middle+b[k]*middle**2+c[k]*middle**3
        lo = np.where(value < target, middle, lo)
        hi = np.where(value >= target, middle, hi)
    return np.asarray(x[k]+h[k]*(lo+hi)/2, float)


def verify(model, times, actual):
    expected = invert(model, times)
    error = float(np.max(abs(expected-actual))/1024)
    assert error <= 2e-11
    x, y, h, a, b, c = coefficients(model)
    k = np.clip(np.searchsorted(x, actual, side='right')-1, 0, len(x)-2)
    s = (np.asarray(actual, np.longdouble)-x[k])/h[k]
    back = y[k]+a[k]*s+b[k]*s*s+c[k]*s*s*s
    closure = float(np.max(abs(back-np.asarray(times, np.longdouble))))
    assert closure <= 2e-12
    return dict(all_queries=len(times), independent_inverse_max_cycles=error, independent_forward_closure_max_seconds=closure)
