"""Independent interpolation, hinge deposition and carrier sums; no producer imports."""
import math
import numpy as np


def interpolate(query, x, y):
    query = np.asarray(query)
    assert query.min() >= x[0] and query.max() <= x[-1]
    j = np.clip(np.searchsorted(x, query, side='right')-1, 0, len(x)-2)
    return y[j]+(query-x[j])/(x[j+1]-x[j])*(y[j+1]-y[j])


def geometry(d, info):
    x, y, q = d['graph_x'], d['graph_y'], d['query']
    assert np.all(np.diff(x)>0) and np.all(np.diff(y)>0) and np.all(np.diff(q)==1)
    assert d['graph_special'].dtype == bool
    error = float(np.max(abs(interpolate(q, x, y)-d['graph'])))
    assert error < 2e-12
    slopes = np.array([(float(y[i+1])-float(y[i]))/(float(x[i+1])-float(x[i])) for i in range(len(x)-1)])
    jumps = np.array([slopes[i+1]-slopes[i] for i in range(len(slopes)-1)])
    assert np.array_equal(slopes, d['slopes']) and np.array_equal(jumps, d['jumps'])
    assert np.array_equal(d['jump_node'], x[1:-1])
    accum = np.zeros((2, len(q)-2)); support = np.zeros(len(q)-2, bool)
    for i, node in enumerate(x[1:-1]):
        position = float(node-q[0]); left = math.floor(position); fraction = position-left
        kind = 0 if d['graph_special'][i+1] else 1
        for at, weight in ((left-1, 1-fraction), (left, fraction)):
            if 0 <= at < len(q)-2:
                accum[kind, at] += jumps[i]*weight
                if kind == 0:
                    support[at] = True
    component_error = []
    for c in (0, 1):
        scale = float(np.max(abs(accum[c])))
        difference = float(np.max(abs(accum[c]-d['components'][c])))
        relative = difference/scale if scale else difference
        assert relative < 2e-12
        component_error.append(relative)
    assert np.array_equal(support, d['special_support'])
    delta = np.diff(d['actual']); curvature = delta[1:]-delta[:-1]
    assert np.array_equal(curvature, d['actual_d2'])
    join = np.diff(d['actual']-d['composed']); join = join[1:]-join[:-1]
    assert np.array_equal(join, d['components'][2])
    assert np.array_equal(curvature-d['components'][:3].sum(axis=0), d['components'][3])
    assert np.max(abs(d['components'][:2].sum(axis=0)-np.diff(d['graph'], 2))) < 2e-12
    gram = np.array([[math.fsum(float(a)*float(b) for a, b in zip(v, w))
                      for w in d['components']] for v in d['components']])
    auto = np.diag(gram)
    scale = np.sqrt(auto[:, None]*auto[None])
    difference = abs(gram-d['Gram'])
    assert not np.count_nonzero(difference[scale == 0])
    gram_error = float(np.max(np.divide(difference, scale, out=np.zeros_like(scale), where=scale>0)))
    assert gram_error < 2e-12
    assert info['query_frames'] == len(q) and info['graph_nodes'] == len(x)
    assert info['special_node_count'] == int(d['graph_special'].sum())
    assert info['special_support_samples'] == int(support.sum())
    assert np.array_equal(d['top_indices'], np.argsort(abs(curvature))[-24:][::-1])
    scalar = dict(graph_vs_composed_max_seconds=np.max(abs(d['graph']-d['composed'])),
        composed_vs_actual_max_seconds=np.max(abs(d['composed']-d['actual'])),
        hinge_vs_graph_d2_max_seconds=np.max(abs(d['components'][:2].sum(axis=0)-np.diff(d['graph'], 2))),
        actual_d2_norm_seconds=np.linalg.norm(curvature), actual_d2_peak_seconds=np.max(abs(curvature)))
    for name, expected in scalar.items():
        assert abs(info[name]-expected) < 2e-12*max(abs(expected), np.finfo(float).tiny)
    assert np.max(abs(np.asarray(info['component_norm_seconds'])-np.linalg.norm(d['components'], axis=1))) < 2e-24
    if np.dot(curvature, curvature):
        ratio = np.dot(curvature[support], curvature[support])/np.dot(curvature, curvature)
        assert abs(info['special_support_squared_d2_fraction']-ratio) < 2e-12
    else:
        assert info['special_support_squared_d2_fraction'] is None
    return dict(independent_graph_max_seconds=error, independent_hinge_relative_errors=component_error,
        all_nodes_slopes_jumps_exact=True, all4x4_signed_Gram_max_relative_error=gram_error,
        no_certified_roundoff_relative_clock_bound=True)


def observed(context):
    d = context
    def carrier(audio, first):
        starts = np.arange(0, len(audio)-4096+1, 256)
        k = np.arange(4096); w = .5-.5*np.cos(2*np.pi*k/4096)
        c, s = w*np.cos(2*np.pi*5*k/1024), -w*np.sin(2*np.pi*5*k/1024)
        rows = []
        for start in starts:
            phase = -2*math.pi*5*(int(start)+first)/1024
            row = (c@audio[start:start+4096]+1j*(s@audio[start:start+4096]))/1024
            rows.append(row*complex(math.cos(phase), math.sin(phase)))
        return starts+first+2048, np.asarray(rows)
    centers, rows = carrier(d['coarse_audio'], int(d['coarse_indices'][0]))
    old_centers, old_rows = carrier(d['coarse_audio'][4096:-4096], 0)
    slots = np.searchsorted(centers, old_centers); rows[slots] = old_rows
    assert np.array_equal(centers, d['observed_centers']) and np.array_equal(slots, d['observed_original_slots'])
    carrier_error = float(np.max(abs(rows-d['observed_rows'])))
    assert carrier_error < 2e-12
    def unwrap(a):
        return np.r_[a[0], a[0]+np.cumsum(np.remainder(np.diff(a)+np.pi, 2*np.pi)-np.pi)]
    theta = unwrap(np.angle(rows[:, 0]))
    correction = (theta-theta[slots[0]])/(10*np.pi)
    old_theta = unwrap(np.angle(old_rows[:, 0]))
    correction[slots] = (old_theta-old_theta[0])/(10*np.pi)
    phase = d['observed_indices']/1024+interpolate(d['observed_indices'], centers, correction)
    hz = interpolate(d['source_clock_times'], d['clock_times'], d['root_hz'])
    middle = np.searchsorted(d['source_clock_times'], round(d['aperture'][0]*48000)/48000)
    increments = (hz[:-1]+hz[1:])/96000
    coarse_phase = np.r_[-np.cumsum(increments[:middle][::-1])[::-1], 0., np.cumsum(increments[middle:])]
    coarse = interpolate(d['coarse_indices']/1024, coarse_phase, d['source_clock_times'])
    inverse = interpolate(d['sample_indices']/1024, phase, d['observed_indices'])
    positions = interpolate(inverse, d['coarse_indices'], d['coarse_positions'])
    errors = dict(carrier_rows_FS=carrier_error,
        observed_correction_cycles=float(np.max(abs(correction-d['observed_correction']))),
        observed_phase_cycles=float(np.max(abs(phase-d['observed_phase']))),
        source_clock_phase_cycles=float(np.max(abs(coarse_phase-d['source_clock_phase']))),
        coarse_positions_seconds=float(np.max(abs(coarse-d['coarse_positions']))),
        actual_positions_seconds=float(np.max(abs(positions-d['positions']))))
    assert max(errors.values()) < 2e-12, errors
    return errors
