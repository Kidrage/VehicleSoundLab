"""Complete graph solution from file QR, without a square triangle copy."""
import numpy as np
from .factor import FileQR
from .triangle import solve


def solve_graph(source, target):
    target = np.asarray(target, dtype='float64')
    vector = target.ndim == 1
    y = target[:, None] if vector else target
    if y.ndim != 2 or y.shape[0] != source.rows or not np.isfinite(y).all():
        raise ValueError('Finite target with complete waveform row dimension required')
    transformed = source.apply(y, True)
    graph = FileQR(source.graph(source.raw.path.parent/'graph.bin'))
    a = solve(graph, transformed[:source.k], True)
    coordinates = np.vstack((a, np.zeros((source.columns, y.shape[1]))))
    reduced = -graph.apply(coordinates)
    reduced[:source.k] = -solve(graph, a)
    z = reduced[source.k:].copy()
    residual = -transformed.copy()
    residual[:source.k] = reduced[:source.k]
    model = source.apply(residual)
    def packed(value):
        return value[:, 0] if vector else value
    return dict(z=packed(z), root_model_residual=packed(model)), graph
