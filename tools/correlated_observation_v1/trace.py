"""Reconstruct saved trust steps and original certificates without solving them again."""
import numpy as np
from absolute_amplitude_v1.amplitude import cost
from joint_trust_v1.constraints import Region
from joint_trust_v1.fit import scales_from_observation


def reconstruct(model, initial, target, plan, settings, fit, certificate, progress=None):
    outer, amplitudes = model.unpack(initial)
    scale = plan['soft_l1_scale']
    scales = scales_from_observation(model, outer, amplitudes, target, scale)
    assert np.array_equal(scales, np.asarray(fit['scales']))
    assert cost(model.prediction(outer, amplitudes)-target, scale) == fit['initial_cost']
    radius, history = settings['initial_radius'], []
    for row in fit['history']:
        assert radius == row['radius']
        prediction, derivative = model.prediction(outer, amplitudes, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]
        residual = prediction-target
        assert cost(residual, scale) == row['before_cost']
        ratio = residual/scale
        curvature = (1+ratio**2)**(-1.5)
        gram = matrix.T@(curvature[:, None]*matrix)
        gradient = matrix.T@(residual/np.sqrt(1+ratio**2))
        region = Region(model, outer, amplitudes, scales, radius, settings)
        checked = certificate(row['qp'], gram, gradient, region, np.sqrt(curvature)[:, None]*matrix)
        new_outer, new_amplitudes, effective, feasible = region.retract(np.asarray(row['qp']['primal_solution']))
        assert feasible == row['feasibility']
        assert np.array_equal(new_outer, np.asarray(row['candidate_outer']))
        assert np.array_equal(new_amplitudes, np.asarray(row['candidate_absolute_amplitudes']))
        candidate = cost(model.prediction(new_outer, new_amplitudes)-target, scale)
        predicted = float(-gradient@effective-.5*effective@gram@effective)
        actual = row['before_cost']-candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(feasible['feasible'] and predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
        assert candidate == row['candidate_cost'] and predicted == row['predicted_reduction']
        assert actual == row['actual_reduction'] and ratio == row['ratio'] and accepted == row['accepted']
        if accepted:
            outer, amplitudes = new_outer, new_amplitudes
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        history.append(dict(iteration=row['iteration'], accepted=accepted, certificate=checked,
            candidate_objective_retraction_radius_exact=True))
        if progress:
            progress(history[-1])
    assert radius == fit['final_radius']
    parameters = model.pack(outer, amplitudes)
    residual = model.original.prediction(parameters)-target
    assert cost(residual, scale) == fit['final_cost']
    assert float(np.linalg.norm(residual)/np.linalg.norm(target)) == fit['normalized_projection_residual']
    return parameters, history
