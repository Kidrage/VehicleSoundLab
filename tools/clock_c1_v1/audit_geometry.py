"""Independent scalar PCHIP slopes and normalized Hermite equations."""
import numpy as np


def verify(d, query_name='query', position_name='positions'):
    x, y, q = d['x'], d['y'], d[query_name]
    h = [np.longdouble(x[i+1])-np.longdouble(x[i]) for i in range(len(x)-1)]
    delta = [(np.longdouble(y[i+1])-np.longdouble(y[i]))/h[i] for i in range(len(h))]
    assert min(h) > 0 and min(delta) > 0
    slope = []
    def endpoint(h0, h1, d0, d1):
        m = ((2*h0+h1)*d0-h0*d1)/(h0+h1)
        if m*d0 <= 0:
            return np.longdouble(0)
        return min(m, 3*d0) if d0*d1 <= 0 else m
    slope.append(endpoint(h[0], h[1], delta[0], delta[1]))
    for k in range(1, len(x)-1):
        w1, w2 = 2*h[k]+h[k-1], h[k]+2*h[k-1]
        slope.append((w1+w2)/(w1/delta[k-1]+w2/delta[k]))
    slope.append(endpoint(h[-1], h[-2], delta[-1], delta[-2]))
    # Normalized interval polynomial Y=y0+A*s+B*s^2+C*s^3, s in[0,1].
    a = np.array([h[k]*slope[k] for k in range(len(h))])
    dy = np.diff(np.asarray(y, np.longdouble))
    b = np.array([3*dy[k]-h[k]*(2*slope[k]+slope[k+1]) for k in range(len(h))])
    c = np.array([-2*dy[k]+h[k]*(slope[k]+slope[k+1]) for k in range(len(h))])
    coefficients = np.stack((c, b, a, np.asarray(y[:-1], np.longdouble)-np.longdouble(y[0])))
    got = d['coefficients']*np.array([np.asarray(h)**3, np.asarray(h)**2, h, np.ones(len(h))])
    coefficient_error = float(np.max(abs(got-coefficients)))
    assert coefficient_error < 2e-12
    mins = []
    for k in range(len(h)):
        candidates = [a[k]/h[k], (a[k]+2*b[k]+3*c[k])/h[k]]
        if c[k] != 0:
            at = -b[k]/(3*c[k])
            if 0 < at < 1:
                candidates.append((a[k]+2*b[k]*at+3*c[k]*at*at)/h[k])
        mins.append(min(candidates))
    mins = np.asarray(mins)
    assert mins.min() > 0
    derivative_error = float(np.max(abs(mins-d['interval_minimum_derivative'])/np.asarray(delta)))
    assert derivative_error < 2e-12
    pc = d['coefficients']; width = np.asarray(h, float)
    right_derivative = (3*pc[0]*width+2*pc[1])*width+pc[2]
    continuity = float(np.max(abs(right_derivative[:-1]-pc[2, 1:])/np.asarray(delta[:-1])))
    assert continuity < 2e-12
    def calc(values):
        assert np.min(values) >= x[0] and np.max(values) <= x[-1]
        output = []
        for value in values:
            k = min(len(x)-2, int(np.searchsorted(x, value, side='right'))-1)
            s = (np.longdouble(value)-np.longdouble(x[k]))/h[k]
            output.append(np.longdouble(y[k])+a[k]*s+b[k]*s*s+c[k]*s*s*s)
        return np.asarray(output, float)
    expected, nodes = calc(q), calc(x)
    query_error = float(np.max(abs(expected-d[position_name])))
    node_error = float(np.max(abs(nodes-y)))
    assert max(query_error, node_error) < 2e-12
    assert abs(float(d['origin'])-float(y[0])) == 0
    return dict(all_queries=len(q), all_intervals=len(h), coordinate_error_seconds=query_error,
        coefficient_scaled_error_seconds=coefficient_error, derivative_relative_error=derivative_error,
        node_error_seconds=node_error, derivative_join_relative_error=continuity,
        minimum_derivative_seconds_per_sample=float(mins.min()))
