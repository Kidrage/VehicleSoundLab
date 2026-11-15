"""Fixed affine, manufactured slope-jump and analytic smooth clock controls."""
import numpy as np
from locked_source_tail_v1.known import evaluate
from .geometry import decompose


NODES = np.array([1024.25, 4096.5, 8192.125, 12288.75, 16384.3])
JUMPS = np.array([1e-8, -6e-9, 4e-9, -7e-9, 3e-9])


def clock(u, origin, kind):
    u = np.asarray(u, float)
    out = origin+u/65536
    if kind == 'affine':
        return out
    d = u[:, None]-NODES[None]
    h = np.maximum(d, 0) if kind == 'C0' else (d+np.sqrt(d*d+256.**2))/2
    return out+h@JUMPS


def qualify(frames, coefficients, frequencies, taps):
    query = np.arange(frames)
    coarse = np.arange(-2048, frames+2048, dtype=float)
    coarse += .003*np.sin(coarse/5000)
    x = np.unique(np.r_[coarse, NODES])
    arrays, cases = {}, []
    for origin in (.36, 160.36):
        for kind in ('affine', 'C0'):
            name = kind+('_large_origin' if origin > 1 else '')
            y = clock(x, origin, kind)
            special = np.isin(x, NODES) if kind == 'C0' else np.zeros(len(x), bool)
            values, info = decompose(x, y, query, special)
            exact = clock(query, origin, kind)
            error = float(np.max(abs(exact-values['graph'])))
            assert error < 2e-12
            if kind == 'C0':
                at = np.searchsorted(x[1:-1], NODES)
                assert np.max(abs(values['jumps'][at]-JUMPS)) < 2e-12
            arrays.update({name+'__'+key: value for key, value in values.items()})
            cases.append(dict(name=name, exact_clock_max_seconds=error, **info))
    smooth_x = clock(x, .36, 'smooth')
    exact_smooth = clock(query, .36, 'smooth')
    target = clock(query, .36, 'C0')
    endpoints = np.array([target[0]-exact_smooth[0], target[-1]-exact_smooth[-1]])
    def correction(u):
        return endpoints[0]+(endpoints[1]-endpoints[0])*(u-query[0])/(query[-1]-query[0])
    exact_smooth += correction(query)
    smooth_graph, smooth_info = decompose(x, smooth_x+correction(x), query, np.zeros(len(x), bool))
    arrays.update({'smooth_PL__'+key: value for key, value in smooth_graph.items()})
    cases.append(dict(name='smooth_PL', **smooth_info))
    clocks = dict(affine=clock(query, .36, 'affine'), manufactured_C0=target,
                  exact_smooth=exact_smooth, sampled_smooth_PL=smooth_graph['graph'])
    values = {name: evaluate(seconds, frequencies, coefficients, taps) for name, seconds in clocks.items()}
    arrays.update({'clock__'+name: value for name, value in clocks.items()})
    arrays.update(nodes=NODES, prescribed_jumps=JUMPS, frequencies=frequencies,
                  coefficients=coefficients, taps=taps)
    mono = evaluate(clocks['affine'], frequencies, np.repeat(coefficients[:, :1], 2, axis=1), taps)
    zero = evaluate(clocks['affine'], frequencies, coefficients*0, taps)
    weak = evaluate(clocks['affine'], frequencies, coefficients*1e-6, taps)
    assert np.array_equal(mono[:, 0], mono[:, 1]) and not np.count_nonzero(zero)
    assert np.max(abs(weak-values['affine']*1e-6)) < 2e-12
    arrays.update(mono=mono, zero=zero, weak=weak)
    rejected = []
    for name, xx, yy, qq, mask in (
        ('nonfinite', x*np.nan, clock(x, .36, 'affine'), query, np.zeros(len(x), bool)),
        ('complex', x.astype(complex), clock(x, .36, 'affine'), query, np.zeros(len(x), bool)),
        ('nonmonotone_x', x[::-1], clock(x, .36, 'affine'), query, np.zeros(len(x), bool)),
        ('nonmonotone_y', x, np.zeros(len(x)), query, np.zeros(len(x), bool)),
        ('unsupported', x, clock(x, .36, 'affine'), query-len(query), np.zeros(len(x), bool)),
        ('nonunit_query', x, clock(x, .36, 'affine'), query*.5, np.zeros(len(x), bool)),
        ('invalid_mask', x, clock(x, .36, 'affine'), query, np.zeros(len(x)))):
        try:
            decompose(xx, yy, qq, mask)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('Invalid geometry accepted: '+name)
    return arrays, values, dict(all_known_qualified=True, cases=cases, rejections=rejected,
        smooth_width_samples=256, diagnostic_reference='exact_smooth',
        smooth_endpoint_matched_manufactured_control_not_actual_clock_candidate=True)
