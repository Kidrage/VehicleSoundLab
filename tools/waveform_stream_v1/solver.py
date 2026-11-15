"""Exact structured graph solve, shared geometry and independent RHS columns."""
import numpy as np
from scipy import linalg
from .householder import Householder
from .metric_root import factor


def solve(forward, adjoint, prior, wave_metric, target, ledger, block=16):
    target = np.asarray(target, float)
    vector = target.ndim == 1
    if target.ndim not in (1, 2) or not np.isfinite(target).all():
        raise ValueError('Finite waveform target vector/matrix required')
    y = target[:, None] if vector else target
    m, n = len(y), prior.size
    if wave_metric.shape != (m, m) or block < 1:
        raise ValueError('Invalid waveform dimensions or block size')
    for name, value in (('penalty.K', prior.K), ('penalty.L', prior.L)):
        ledger.add(name, value)
    root=factor(wave_metric,ledger)
    metric_alias=root.shares_input
    t = root.transpose(y)
    ledger.add('weighted_target', t)
    X = np.empty((m, n), order='F')
    ledger.add('weighted_synthesis', X)
    for first in range(0, n, block):
        last = min(n, first+block)
        raw = np.empty((m, last-first), order='F')
        ledger.add('source_block.'+str(first), raw)
        basis = np.zeros(n)
        for j in range(first, last):
            basis[j] = 1
            raw[:, j-first] = forward(basis)
            basis[j] = 0
        X[:, first:last] = root.transpose(raw)
    del raw, basis
    for first in range(0, m, block):
        last = min(m, first+block)
        X[first:last] = prior.inverse(X[first:last].T).T
    normA = float(np.sqrt(np.einsum('ij,ij->', X, X)+n))
    ledger.snapshot('weighted_synthesis.penalty_whitened')
    qr = Householder(X, ledger, 'X_QR')
    del X
    k = qr.k
    transformed = qr.apply(t, True)
    D = np.empty((k+n, k), order='F')
    ledger.add('graph.input', D)
    qr.graph_into(D, block)
    graph = Householder(D, ledger, 'graph_QR')
    del D
    T = graph.square_triangular()
    a = linalg.solve_triangular(T, transformed[:k], trans='T', lower=False, check_finite=False)
    ledger.add('graph.coordinates', a)
    coordinates = np.vstack((a, np.zeros((n, y.shape[1]))))
    reduced = -graph.apply(coordinates)
    reduced[:k] = -linalg.solve_triangular(T, a, lower=False, check_finite=False)
    z = reduced[k:].copy()
    q = prior.inverse_transpose(z)
    residual_coordinates = -transformed.copy()
    residual_coordinates[:k] = reduced[:k]
    model = qr.apply(residual_coordinates)
    wave_model = root.solve_transpose(model)
    # Multiple RHS are never averaged. Original complete actions are repeated
    # independently; the QR and graph factors alone are shared.
    def apply_X(value):
        return np.column_stack([root.transpose(forward(prior.inverse_transpose(v))) for v in value.T])
    def apply_XT(value):
        return np.column_stack([prior.inverse(adjoint(root.apply(v))) for v in value.T])
    direct = apply_X(z)-t
    normal = apply_XT(direct)+z
    stable_normal = apply_XT(model)+z
    def normal_ratio(g, residual):
        return np.linalg.norm(g, axis=0)/np.maximum(normA*np.sqrt(np.sum(residual**2+0., axis=0)+np.sum(z*z, axis=0)), 1e-300)
    direct_ratio = normal_ratio(normal, direct)
    stable_ratio = normal_ratio(stable_normal, model)
    backward = np.linalg.norm(direct-model, axis=0)/np.maximum(np.linalg.norm(t, axis=0), 1e-300)
    for name, value in (('q', q), ('z', z), ('root.model', model), ('wave.model', wave_model)):
        ledger.add(name, value)
    ledger.snapshot('solve.complete')
    def packed(value):
        return value[:, 0] if vector else value
    values = dict(q=packed(q), z=packed(z), t=packed(t), x_raw=qr.raw,
        x_reflectors=qr.reflectors, x_tau=qr.tau,
        graph_reflectors=graph.reflectors, graph_tau=graph.tau, graph_R=T,
        transformed_target=packed(transformed), graph_coordinates=packed(a),
        reduced_model_residual=packed(reduced), root_model_residual=packed(model),
        wave_model_residual=packed(wave_model), direct_transformed_normal=packed(normal),
        stable_root_normal=packed(stable_normal), temporal_K=prior.K, temporal_L=prior.L)
    def number(value):
        return float(value[0]) if vector else value.tolist()
    info = dict(method='direct_geqrf_structured_graph_independent_RHS',
        waveform_rows=m, source_columns=n, RHS=y.shape[1], retained_QR_directions=k, block=block,
        metric_root_shares_input=metric_alias, metric_root_type=root.kind,X_QR_alias=qr.alias, graph_QR_alias=graph.alias,
        geqrf_lwork=[qr.lwork, graph.lwork],
        graph_triangular_explicit_F_copy=True,
        rectangular_R_or_explicit_Q_or_dense_packed_R_allocated_by_solver=False,
        explicit_Q_or_dense_packed_R_allocated_by_solver=False,
        complete_normal_uses_original_synthesis_adjoint=True,
        original_direct_whitened_normal_relative=number(direct_ratio),
        original_direct_whitened_normal_passed=bool(np.all(direct_ratio <= 1e-11)),
        stable_root_normal_relative=number(stable_ratio), root_backward_discrepancy=number(backward),
        stable_root_guard_passed=bool(np.all(stable_ratio <= 1e-11) and np.all(backward <= 1e-11)),
        augmented_root_Frobenius=normA, no_order_node_rank_rate_reduction=True)
    return values, info
