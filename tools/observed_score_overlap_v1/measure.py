"""Frozen score covariance, not an estimator or latent-phase uncertainty."""
import numpy as np
from aperture_model_v1.forward import real_rows
from complex_radial_v1.loss import gradient, hessian_apply
from .pullback import accumulate


def phase_samples(model, parameters):
    samples, jacobian = model.samples(parameters, True)
    start = 2*model.parts
    return samples, jacobian[:, start:start+model.phase_count]


def measure(operator, samples, derivative, audio, scale, direction):
    residual = real_rows(operator.apply(samples-audio))
    projected = real_rows(operator.apply(derivative))
    weighted = hessian_apply(residual, projected, scale)
    total, full, independent = accumulate(operator, weighted, len(samples))
    score = projected.T@gradient(residual, scale)
    diag, surrogate = full.diagonal(), independent.diagonal()
    ratio = np.divide(diag, surrogate, out=np.zeros_like(diag), where=surrogate > 0)
    full_direction = float(direction@full@direction)
    independent_direction = float(direction@independent@direction)
    result = dict(phase_columns=derivative.shape[1], windows=len(operator.starts),
        overlap_samples=int(operator.size-np.diff(operator.starts)[0]),
        diagonal_full_over_independent_minimum=float(ratio.min()),
        diagonal_full_over_independent_median=float(np.median(ratio)),
        diagonal_full_over_independent_maximum=float(ratio.max()),
        directional_full_variance=full_direction,
        directional_independent_variance=independent_direction,
        directional_full_over_independent=full_direction/independent_direction if independent_direction > 0 else None,
        unit_source_white_noise=True, real_noise_calibrated=False, nuisance_profiled=False,
        fitted_phase_uncertainty=False)
    return result, dict(source_pullback=total, full_covariance=full,
        independent_window_covariance=independent, score=score, variance_ratios=ratio,
        residual=residual, projected_phase_derivative=projected, weighted_phase_derivative=weighted)
