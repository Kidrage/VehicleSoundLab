"""Exact PL hinge identity with signed residuals for finite precision and joins."""
import numpy as np


def decompose(x, y, query, special, actual=None, composed=None):
    x, y, query, special = map(np.asarray, (x, y, query, special))
    if (x.ndim != 1 or len(x) < 3 or y.shape != x.shape or special.shape != x.shape
            or special.dtype != bool or query.ndim != 1 or len(query) < 3
            or any(np.iscomplexobj(v) or not np.isfinite(v).all() for v in (x, y, query))
            or np.any(np.diff(x) <= 0) or np.any(np.diff(y) <= 0)
            or not np.array_equal(np.diff(query), np.ones(len(query)-1))
            or query[0] < x[0] or query[-1] > x[-1]):
        raise ValueError('Finite increasing graph, unit-step supported query and boolean node mask required')
    graph = np.interp(query, x, y)
    actual = graph if actual is None else np.asarray(actual)
    composed = graph if composed is None else np.asarray(composed)
    for value in (actual, composed):
        if value.shape != query.shape or np.iscomplexobj(value) or not np.isfinite(value).all():
            raise ValueError('Finite complete actual and composed queries required')
    slope = np.diff(y)/np.diff(x)
    jumps = np.diff(slope)
    node = x[1:-1]-query[0]
    m = np.floor(node).astype(np.int64)
    fraction = node-m
    component = np.zeros((4, len(query)-2))
    support = np.zeros(len(query)-2, bool)
    for shift, weight in ((-1, 1-fraction), (0, fraction)):
        ids = m+shift
        valid = (ids >= 0) & (ids < component.shape[1])
        kind = (~special[1:-1][valid]).astype(int)
        np.add.at(component, (kind, ids[valid]), jumps[valid]*weight[valid])
        support[ids[valid & special[1:-1]]] = True
    component[2] = np.diff(actual-composed, 2)
    actual_d2 = np.diff(actual, 2)
    component[3] = actual_d2-component[:3].sum(axis=0)
    gram = component@component.T
    total = float(np.dot(actual_d2, actual_d2))
    closure = abs(total-float(gram.sum()))/float(np.sum(abs(gram))) if np.count_nonzero(gram) else 0.
    assert closure < 2e-12
    top = np.argsort(abs(actual_d2))[-24:][::-1]
    arrays = dict(graph_x=x, graph_y=y, graph_special=special, query=query,
        graph=graph, actual=actual, composed=composed, slopes=slope,
        jump_node=x[1:-1], jumps=jumps, actual_d2=actual_d2,
        components=component, Gram=gram, special_support=support, top_indices=top)
    info = dict(query_frames=len(query), graph_nodes=len(x),
        special_node_count=int(np.count_nonzero(special)),
        graph_vs_composed_max_seconds=float(np.max(abs(graph-composed))),
        composed_vs_actual_max_seconds=float(np.max(abs(composed-actual))),
        hinge_vs_graph_d2_max_seconds=float(np.max(abs(component[:2].sum(axis=0)-np.diff(graph, 2)))),
        component_names=['observed_phase_nodes', 'other_coarse_grid_nodes', 'original_preservation_join', 'floating_evaluation_remainder'],
        component_norm_seconds=np.linalg.norm(component, axis=1).tolist(),
        actual_d2_norm_seconds=float(np.linalg.norm(actual_d2)),
        actual_d2_peak_seconds=float(np.max(abs(actual_d2))),
        special_support_samples=int(np.count_nonzero(support)),
        special_support_squared_d2_fraction=float(np.dot(actual_d2[support], actual_d2[support])/total) if total else None,
        signed_Gram_closure_relative=closure,
        curvature_is_not_acoustic_power=True, component_norms_not_independent_percentages=True,
        absolute_geometry_gate_seconds=2e-12, not_certified_roundoff_relative_error=True)
    assert info['hinge_vs_graph_d2_max_seconds'] < 2e-12
    return arrays, info


def reconstruct(context):
    d = context
    rows, slots = d['observed_rows'], d['observed_original_slots']
    angle = np.unwrap(np.angle(rows[:, 0]))
    correction = (angle-angle[slots[0]])/(10*np.pi)
    original_angle = np.unwrap(np.angle(rows[slots, 0]))
    correction[slots] = (original_angle-original_angle[0])/(10*np.pi)
    phase = d['observed_indices']/1024+np.interp(d['observed_indices'], d['observed_centers'], correction)
    hz = np.interp(d['source_clock_times'], d['clock_times'], d['root_hz'])
    dq = (hz[:-1]+hz[1:])/96000
    middle = np.searchsorted(d['source_clock_times'], round(d['aperture'][0]*48000)/48000)
    coarse_phase = np.r_[-np.cumsum(dq[:middle][::-1])[::-1], 0., np.cumsum(dq[middle:])]
    coarse = np.interp(d['coarse_indices']/1024, coarse_phase, d['source_clock_times'])
    at = np.interp(d['sample_indices']/1024, phase, d['observed_indices'])
    composed = np.interp(at, d['coarse_indices'], d['coarse_positions'])
    arrays = dict(rebuilt_correction=correction, rebuilt_phase=phase,
                  rebuilt_source_clock_phase=coarse_phase, rebuilt_coarse_positions=coarse, inverse_at=at)
    checks = {}
    for key, value in (('correction', correction), ('phase', phase), ('source_clock_phase', coarse_phase), ('coarse_positions', coarse)):
        expected = d['observed_'+key] if key in ('correction', 'phase') else d[key]
        error = float(np.max(abs(value-expected)))
        assert error < 2e-12, (key, error)
        checks[key] = error
    graph_y = d['coarse_positions'][(d['observed_indices']-d['coarse_indices'][0]).astype(int)]
    geom, info = decompose(phase*1024, graph_y, d['sample_indices'],
        np.isin(d['observed_indices'], d['observed_centers']), d['positions'], composed)
    assert info['composed_vs_actual_max_seconds'] < 2e-12
    arrays.update(geom)
    return arrays, dict(info, upstream_reconstruction_max_errors=checks,
        two_stage_inverse_and_target_preservation_verified=True,
        acoustic_coordinate_not_physical_crank_RPM=True)
