"""Stream original synthesis and node whitening into file QR; no dense X."""
import numpy as np
from waveform_stream_v1.metric_root import factor
from .store import FileMatrix
from .factor import FileQR
from .graph import solve_graph


def solve_file(forward, prior, metric, target, directory, ledger, block):
    target = np.asarray(target, dtype='float64')
    vector = target.ndim == 1
    if target.ndim not in (1, 2) or not np.isfinite(target).all():
        raise ValueError('Finite complete waveform target required')
    y = target[:, None] if vector else target
    m, n = len(y), prior.size
    if metric.shape != (m, m):
        raise ValueError('Complete waveform metric must match all rows')
    root = factor(metric, ledger)
    t = root.transpose(y)
    ledger.add('fileSolver.weighted_target', t)
    X = FileMatrix(directory/'source.bin', (m, n), block, ledger)
    basis = np.zeros(n)
    ledger.add('fileSolver.source_basis', basis)
    for first in range(0, n, block):
        last = min(first+block, n)
        raw = np.empty((m, last-first), order='F')
        ledger.add('fileSolver.source_column_panel', raw)
        for j in range(first, last):
            basis[j] = 1.
            raw[:, j-first] = forward(basis)
            basis[j] = 0.
        weighted = root.transpose(raw)
        ledger.add('fileSolver.weighted_column_panel', weighted)
        X.write(0, m, first, last, weighted)
        ledger.snapshot('fileSolver.source_column_panel.written')
        del raw, weighted
    del basis
    norm_squared = float(n)
    for first in range(0, m, block):
        last = min(first+block, m)
        raw = X.read(first, last, 0, n)
        whitened = prior.inverse(raw.T).T
        ledger.add('fileSolver.whitened_row_panel', whitened)
        X.write(first, last, 0, n, whitened)
        norm_squared += float(np.einsum('ij,ij->', whitened, whitened))
        ledger.snapshot('fileSolver.penalty_row_panel.written')
        del raw, whitened
    source = FileQR(X)
    base, graph = solve_graph(source, t)
    base['q'] = prior.inverse_transpose(base['z'])
    base['wave_model_residual'] = root.solve_transpose(base['root_model_residual'])
    if vector:
        base = {name:value[:, 0] for name, value in base.items()}
    ledger.snapshot('fileSolver.complete')
    return base, source, graph, dict(method='bounded_file_complete_graph', waveform_rows=m,
        source_columns=n, RHS=y.shape[1], retained_QR_directions=min(m, n), block=block,
        metric_root_type=root.kind, metric_root_shares_input=root.shares_input,
        augmented_root_Frobenius=float(np.sqrt(norm_squared)),
        complete_source_streamed=True, source_whitening_rows_streamed=True,
        no_dense_X_or_graph_or_square_T_or_full_Q=True,
        no_order_node_rank_rate_context_or_scale_reduction=True)
