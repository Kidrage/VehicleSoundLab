"""Fixed source-space model scores; all initial tangent columns are retained."""
import numpy as np
from .adjoint import native_adjoint


def build(model, initial):
    outer, controls = model.unpack(initial)
    _, phase = model.prediction(outer, controls, True)
    jacobian = np.column_stack((phase, model.design(outer)))
    raw = native_adjoint(model.original.aperture, jacobian, len(model.original.time))
    norms = np.linalg.norm(raw, axis=0)
    if np.any(norms <= 0):
        raise ArithmeticError('Initial model score has an identically zero column')
    normalized = raw/norms[None, :]
    basis, singular, right = np.linalg.svd(normalized, full_matrices=False)
    if len(singular) != jacobian.shape[1] or singular.min() <= 0:
        raise ArithmeticError('Complete initial tangent is not represented')
    # A deterministic sign convention leaves the full source subspace intact.
    peaks = np.argmax(abs(basis), axis=0)
    signs = np.where(basis[peaks, np.arange(len(singular))] >= 0, 1., -1.)
    basis *= signs[None, :]
    right *= signs[:, None]
    return basis, dict(singular_values=singular.tolist(), column_norms=norms.tolist(),
        source_frames=len(raw), source_parameters=jacobian.shape[1], retained_scores=basis.shape[1],
        normalized_adjoint_jacobian_condition=float(singular.max()/singular.min()),
        tangent_reconstruction_relative_error=float(np.linalg.norm((basis*singular)@right-normalized)/np.linalg.norm(normalized)),
        original_observed_initial_only=True, heldout_used=False, truth_used=False, rank_truncation=False)


class ScoreAperture:
    def __init__(self, basis, native):
        self.basis = basis
        self.real_noise_variance = 2*np.sum(native.window**2)/native.window.sum()**2
        self.scale = np.sqrt(self.real_noise_variance)
        self.real_scores = basis.shape[1]

    def real_apply(self, values):
        return self.scale*(self.basis.T@values)

    def apply(self, values):
        # Existing model code applies real_rows to every result. Pack the real
        # moments so that this restores their exact order, padding only if odd.
        vector = values.ndim == 1
        real = self.real_apply(values)
        rows = real[:, None] if vector else real
        if len(rows)%2:
            rows = np.vstack((rows, np.zeros((1, rows.shape[1]))))
        half = len(rows)//2
        packed = rows[:half]+1j*rows[half:]
        return packed[:, 0] if vector else packed
