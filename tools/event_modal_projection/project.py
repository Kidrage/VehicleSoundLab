"""Column-normalized pivoted QR with explicit conditioning and energy checks."""
import numpy as np
from scipy import linalg


def fit(design, audio, mask=None, maximum_condition=1e5):
    a = np.asarray(design, dtype=float)
    x = np.asarray(audio, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if a.ndim != 2 or x.ndim != 2 or len(a) != len(x) or not a.shape[1]:
        raise ValueError('Matching native design and audio required')
    if not np.isfinite(a).all() or not np.isfinite(x).all():
        raise ValueError('Finite design and samples required')
    if mask is None:
        mask = np.ones(len(a), dtype=bool)
    mask = np.asarray(mask)
    if mask.shape != (len(a),) or mask.dtype != bool or mask.sum() <= a.shape[1]:
        raise ValueError('Boolean selection with more rows than columns required')
    if not np.isfinite(maximum_condition) or maximum_condition < 1:
        raise ValueError('Finite condition ceiling>=1 required')
    selected = a[mask]
    scale = np.sqrt(np.mean(selected**2, axis=0))
    if np.any(scale == 0) or not np.isfinite(scale).all():
        raise ValueError('Every normalized carrier column must have support')
    q, r, pivot = linalg.qr(selected/scale, mode='economic', pivoting=True)
    singular = linalg.svdvals(r)
    rank = int(np.count_nonzero(singular > singular[0]*1e-10))
    condition = float(singular[0]/max(singular[-1], np.finfo(float).tiny))
    if rank != a.shape[1] or condition > maximum_condition:
        raise ValueError('Rank or condition unsupported: '+str((rank, a.shape[1], condition)))
    coefficient = np.empty((a.shape[1], x.shape[1]))
    coefficient[pivot] = linalg.solve_triangular(r, q.T@x[mask])
    coefficient /= scale[:, None]
    harmonic = a@coefficient
    remainder = x-harmonic
    normal = (selected/scale).T@remainder[mask]/mask.sum()
    return harmonic, remainder, coefficient, dict(rank=rank, condition=condition,
        rows_fitted=int(mask.sum()), columns=a.shape[1], minimum_column_rms=float(scale.min()),
        maximum_column_rms=float(scale.max()), singular_max=float(singular[0]),
        singular_min=float(singular[-1]), max_normal_residual_FS=float(abs(normal).max()),
        coefficient_origin='Original unit-amplitude basis; old modal amplitudes not used')


def energy(source, harmonic, remainder, mask=None):
    if mask is not None:
        source, harmonic, remainder = (v[mask] for v in (source, harmonic, remainder))
    full, coherent, residual = (float(np.mean(v**2)) for v in (source, harmonic, remainder))
    cross = float(2*np.mean(harmonic*remainder))
    return dict(source_FS2=full, projection_FS2=coherent, remainder_FS2=residual,
        signed_cross_FS2=cross, balance_error_FS2=full-coherent-residual-cross,
        explained_SSE_fraction=float(1-residual/max(full, 1e-300)),
        projection_to_source_power=coherent/max(full, 1e-300))
