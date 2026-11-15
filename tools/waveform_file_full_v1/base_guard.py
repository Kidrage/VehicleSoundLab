"""Original root-normal/backward guard using the already-factored band root."""
import numpy as np
from scipy import linalg
from waveform_banded_v1.root import BandedRoot


def inspect(metric, info, base, audio, forward, adjoint, prior, ledger):
    if not info['metric_root_shares_input'] or not metric.consumed:
        raise RuntimeError('Declared in-place band root unavailable for original base guard')
    # Non-owning diagnostic view of the existing native root; no refactor,
    # dense metric, extra full-band copy or replacement root implementation.
    root = object.__new__(BandedRoot)
    root.L = metric.bands
    root.bandwidth, root.frames = root.L.shape[0]-1, root.L.shape[1]
    root.ledger = ledger
    root.tbmv = linalg.get_blas_funcs('tbmv', (root.L,))
    root.tbsv = linalg.get_blas_funcs('tbsv', (root.L,))
    model = root.transpose(base['wave_model_residual'])
    weighted = root.apply(model)
    normal = np.column_stack([prior.inverse(adjoint(v)) for v in weighted.T])+base['z']
    predicted = np.column_stack([forward(v) for v in base['q'].T])
    direct = root.transpose(predicted-audio)
    t = root.transpose(audio)
    denominator = info['augmented_root_Frobenius']*np.sqrt(np.sum(model*model, axis=0)+np.sum(base['z']**2, axis=0))
    stable = np.linalg.norm(normal, axis=0)/np.maximum(denominator, 1e-300)
    backward = np.linalg.norm(direct-model, axis=0)/np.maximum(np.linalg.norm(t, axis=0), 1e-300)
    passed = bool(np.all(stable <= 1e-11) and np.all(backward <= 1e-11))
    return dict(stable_root_normal_relative=stable.tolist(), root_backward_discrepancy=backward.tolist(),
        stable_root_guard_passed=passed, guard_uses_original_same_inplace_band_root=True)
