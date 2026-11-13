"""Same original joint path with equivalent unit-box QP implementation."""
import numpy as np
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from complex_radial_v1.fit import scales_from_observation
from complex_radial_v1.loss import cost
from radial_majorizer_v1.geometry import quadratic
from .solver import solve
from residual_scale_bootstrap_v1.scale import choose


def estimate(model, audio, plan, variant, settings, initial, progress=None):
    outer, controls = model.unpack(initial)
    target = real_rows(model.original.aperture.apply(audio[:, 0])); floor = plan['soft_l1_scale']
    initial_residual = model.prediction(outer, controls)-target
    initial_scale, initial_median = choose(initial_residual, floor)
    scales = scales_from_observation(model, outer, controls, target, initial_scale)
    radius = settings['initial_radius']; history = []
    for iteration in range(1, settings['maximum_iterations']+1):
        value, phase = model.prediction(outer, controls, True)
        matrix = np.column_stack((phase, model.design(outer)))*scales[None, :]
        residual = value-target; stage, median = choose(residual, floor)
        before, original_before = cost(residual, stage), cost(residual, floor)
        gram, gradient, weighted, rhs = quadratic(residual, matrix, stage)
        region = Region(model, outer, controls, scales, radius, settings)
        step, qp = solve(gram, gradient, weighted, rhs, region, settings)
        new_outer, new_controls, effective, feasible = region.retract(step)
        predicted = float(-gradient@effective-.5*effective@gram@effective)
        candidate_residual = model.prediction(new_outer, new_controls)-target
        candidate = cost(candidate_residual, stage); original_candidate = cost(candidate_residual, floor)
        actual = before-candidate; original_actual = original_before-original_candidate
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(qp['success'] and feasible['feasible'] and predicted > 0 and actual > 0
            and ratio >= settings['acceptance_ratio'] and original_actual > 0)
        row = dict(iteration=iteration, radius=radius, stage_scale=stage, observed_residual_median=median,
            before_cost=before, candidate_cost=candidate, original_before_cost=original_before,
            original_candidate_cost=original_candidate, predicted_reduction=predicted,
            actual_reduction=actual, original_actual_reduction=original_actual, ratio=ratio, accepted=accepted,
            scaled_step_maximum=float(abs(effective).max()), qp=qp, feasibility=feasible,
            candidate_outer=new_outer.tolist(), candidate_absolute_amplitudes=new_controls.tolist())
        if accepted: outer, controls = new_outer, new_controls
        history.append(row)
        if progress: progress(row)
        if not accepted or ratio < .25: radius *= .25
        elif ratio > .75 and abs(effective).max() > .8*radius: radius = min(2*radius, settings['maximum_radius'])
        if radius < settings['minimum_radius']: break
    parameters = model.pack(outer, controls); _, phase, envelope = model.original.samples(parameters)
    residual = model.original.prediction(parameters)-target; normalized = float(np.linalg.norm(residual)/np.linalg.norm(target))
    final_scale, final_median = choose(residual, floor)
    amplitude = np.hypot(parameters[:model.parts], parameters[model.parts:2*model.parts])
    remaining = sum(amplitude[k] >= plan['rules']['minimum_carrier_amplitude'] for k in range(model.parts) if k not in model.original.selected)
    low, high = model.original.bounds(plan, variant)
    assert max(np.max(low-parameters), np.max(parameters-high)) <= 1e-9
    minimum_step = float(np.diff(model.original.time+phase).min())
    return parameters, phase, dict(history=history, iterations=len(history), accepted_steps=sum(row['accepted'] for row in history),
        initial_cost=cost(initial_residual, floor), final_cost=cost(residual, floor),
        initial_stage_scale=initial_scale, initial_residual_median=initial_median, final_stage_scale=final_scale,
        final_residual_median=final_median, original_scale_reached=bool(final_scale == floor), final_radius=radius,
        normalized_projection_residual=normalized, remaining_carriers=int(remaining), minimum_envelope=float(envelope.min()),
        maximum_envelope=float(envelope.max()), minimum_coordinate_step=minimum_step,
        observation_supported=bool(normalized <= variant['maximum_normalized_projection_residual'] and
            remaining >= variant['minimum_remaining_carriers'] and envelope.min() > 0 and minimum_step > 0),
        scales=scales.tolist(), truth_used=False, heldout_used=False, extra_initialization_iterations=0,
        curvature='radial_concave_power_tangent_vI2', schedule='original_joint_all_variables',
        initial_scales_from_original_exact_H=True,
        convergence='Residual-space majorization only; original nonlinear acceptance unchanged, no global guarantee')
