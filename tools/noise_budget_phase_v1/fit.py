"""Finite feasible-start SQP: phase jerk minimum within observed noise energy."""
import numpy as np
from aperture_model_v1.forward import real_rows
from absolute_amplitude_v1.amplitude import cost
from joint_trust_v1.fit import scales_from_observation
from joint_trust_v1.constraints import Region
from .conic import solve_region


def estimate(model, audio, plan, variant, settings, initial, roughness, noise_radius, progress=None):
    outer, controls = model.unpack(initial)
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    scales = scales_from_observation(model, outer, controls, target, plan['soft_l1_scale'])
    radius, multiplier = settings['initial_radius'], 0.
    history = []
    initial_noise_ratio = float(np.linalg.norm(model.prediction(outer, controls)-target)/noise_radius)
    assert initial_noise_ratio < 1., 'Only the observed discrepancy feasible start is authorized'
    for iteration in range(1, settings['maximum_iterations']+1):
        predicted, derivative = model.prediction(outer, controls, True)
        matrix = np.column_stack((derivative, model.design(outer)))*scales[None, :]/noise_radius
        residual = (predicted-target)/noise_radius
        rough = np.column_stack((roughness, np.zeros((len(roughness), controls.size))))*scales[None, :]
        phase = roughness@outer
        region = Region(model, outer, controls, scales, radius, settings)
        step, subproblem = solve_region(matrix, residual, rough, phase, region, settings)
        new_outer, new_controls, effective, feasible = region.retract(step)
        multiplier = max(multiplier, settings['merit_dual_multiplier']*subproblem['original_noise_dual_alpha'])
        before_roughness = float(.5*np.dot(phase, phase))
        before_violation = float(max(0., np.linalg.norm(residual)-1))
        new_phase = roughness@new_outer
        candidate_roughness = float(.5*np.dot(new_phase, new_phase))
        linear_violation = float(max(0., np.linalg.norm(residual+matrix@effective)-1))
        actual_residual = (model.prediction(new_outer, new_controls)-target)/noise_radius
        candidate_violation = float(max(0., np.linalg.norm(actual_residual)-1))
        predicted_reduction = before_roughness+multiplier*before_violation-candidate_roughness-multiplier*linear_violation
        actual_reduction = before_roughness+multiplier*before_violation-candidate_roughness-multiplier*candidate_violation
        ratio = actual_reduction/predicted_reduction if predicted_reduction > 0 else None
        accepted = bool(subproblem['success'] and feasible['feasible'] and predicted_reduction > 0
            and actual_reduction > 0 and ratio >= settings['acceptance_ratio'])
        row = dict(iteration=iteration, radius=radius, merit_multiplier=multiplier,
            before_roughness=before_roughness, candidate_roughness=candidate_roughness,
            before_noise_violation=before_violation, candidate_noise_violation=candidate_violation,
            linearized_noise_violation=linear_violation, predicted_reduction=predicted_reduction,
            actual_reduction=actual_reduction, ratio=ratio, accepted=accepted,
            scaled_step_maximum=float(abs(effective).max()), subproblem=subproblem, feasibility=feasible,
            candidate_outer=new_outer.tolist(), candidate_absolute_amplitudes=new_controls.tolist())
        history.append(row)
        if progress:
            progress(row)
        if accepted:
            outer, controls = new_outer, new_controls
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        if radius < settings['minimum_radius']:
            break
    parameters = model.pack(outer, controls)
    _, phase, envelope = model.original.samples(parameters)
    residual = model.original.prediction(parameters)-target
    norm = float(np.linalg.norm(residual))
    normalized = float(norm/np.linalg.norm(target))
    amplitude = np.hypot(parameters[:model.parts], parameters[model.parts:2*model.parts])
    remaining = sum(amplitude[k] >= plan['rules']['minimum_carrier_amplitude']
        for k in range(model.parts) if k not in model.original.selected)
    low, high = model.original.bounds(plan, variant)
    assert max(np.max(low-parameters), np.max(parameters-high)) <= 1e-9
    return parameters, phase, dict(history=history, iterations=len(history), accepted_steps=sum(r['accepted'] for r in history),
        conic_subproblems_certified=sum(r['subproblem']['success'] for r in history),
        original_conic_certificates_passed=sum(r['subproblem']['original_certificate']['success'] for r in history),
        initial_noise_ratio=initial_noise_ratio, final_noise_ratio=norm/noise_radius,
        noise_budget_feasible=bool(norm/noise_radius <= 1+settings['maximum_primal_violation']),
        final_roughness=float(.5*np.linalg.norm(roughness@outer)**2),
        original_soft_l1_cost=cost(residual, plan['soft_l1_scale']), normalized_projection_residual=normalized,
        observation_supported=bool(normalized <= variant['maximum_normalized_projection_residual']
            and remaining >= variant['minimum_remaining_carriers'] and envelope.min() > 0
            and np.diff(model.original.time+phase).min() > 0),
        scales=scales.tolist(), final_radius=radius, final_merit_multiplier=multiplier,
        convergence='Finite nonlinear merit/trust-region budget; no convergence or full qualification claim',
        truth_used=False, heldout_used=False)
