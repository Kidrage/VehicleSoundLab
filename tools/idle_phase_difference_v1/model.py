"""Train-only nested power regression, with explicit positivity limits."""
import numpy as np


def fit(feature, power):
    reference = power.mean(axis=0)
    if np.any(reference <= 0) or not np.isfinite(power).all():
        raise ValueError('Positive finite band powers required')
    design = np.column_stack((np.ones(len(feature)), feature))
    coefficient, _, rank, singular = np.linalg.lstsq(design, power / reference, rcond=None)
    count = feature.shape[1] // 2
    radius = np.hypot(coefficient[1:1+count], coefficient[1+count:]).sum(axis=0)
    lower, upper = coefficient[0] - radius, coefficient[0] + radius
    return dict(reference_power=reference.tolist(), coefficients=coefficient.tolist(),
                lower_bound=lower.tolist(), upper_bound=upper.tolist(),
                positive_sufficient_bound=bool(np.all(lower > 0)), rank=int(rank),
                full_rank=bool(rank == design.shape[1]), singular_values=singular.tolist(),
                condition=float(singular[0] / singular[-1]))


def predict(model, feature):
    return np.column_stack((np.ones(len(feature)), feature)) @ np.asarray(model['coefficients'])


def assess(model, feature, power):
    target = power / np.asarray(model['reference_power'])
    predicted = predict(model, feature)
    residual = target - predicted
    constant_error = np.mean((target - np.asarray(model['coefficients'])[0])**2, axis=0)
    error = np.mean(residual**2, axis=0)
    correlation = []
    for a, b in zip(target.T, predicted.T):
        u, v = a-a.mean(), b-b.mean()
        norm = np.linalg.norm(u) * np.linalg.norm(v)
        correlation.append(float(u @ v / norm) if norm else None)
    return dict(constant_mse=constant_error.tolist(), mse=error.tolist(),
                improvement_over_own_constant=(1-error/constant_error).tolist(),
                correlation=correlation, minimum_prediction=predicted.min(axis=0).tolist(),
                mean_target=target.mean(axis=0).tolist(), mean_prediction=predicted.mean(axis=0).tolist(),
                mean_residual=residual.mean(axis=0).tolist(), residual_variance=residual.var(axis=0).tolist())


def decision(rows):
    real = np.asarray(rows[0]['incremental_check_improvement'])
    controls = np.asarray([row['incremental_check_improvement'] for row in rows[1:]])
    supported = (real > 0) & np.all(real > controls, axis=0)
    expanded = rows[0]['models']['expanded']
    return dict(supported_bands=supported.tolist(),
                future_synthesis_prerequisite=bool(supported.sum() >= 3 and expanded['full_rank']
                                                  and expanded['positive_sufficient_bound']))
