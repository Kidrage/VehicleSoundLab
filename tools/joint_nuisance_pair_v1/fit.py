"""Finite original-budget joint a/b and slow-envelope Gauss-Newton trust steps."""
import numpy as np
from .quadratic import solve


def fit(model, target, initial, settings, progress=None):
    x = initial.copy()
    _, jacobian = model.samples(x, True)
    half_width = (model.upper-model.lower)/2
    norms = np.linalg.norm(jacobian, axis=0)
    scales = np.minimum(1/np.maximum(norms, 1e-30), half_width)
    radius = settings['initial_radius']
    history = []
    initial_cost = float(.5*np.sum((model.samples(x)-target)**2))
    for iteration in range(1, settings['maximum_iterations']+1):
        values, jacobian = model.samples(x, True)
        residual = values-target
        design = jacobian*scales[None, :]
        lower = np.maximum((model.lower-x)/scales, -radius)
        upper = np.minimum((model.upper-x)/scales, radius)
        step, result = solve(design, -residual, lower, upper, settings)
        candidate = x+scales*step
        violation = float(max(0., (model.lower-candidate).max(), (candidate-model.upper).max()))
        before = float(.5*(residual@residual))
        next_residual = model.samples(candidate)-target
        cost = float(.5*(next_residual@next_residual))
        predicted = -result['qp']['objective']
        actual = before-cost
        ratio = actual/predicted if predicted > 0 else None
        accepted = bool(result['certificate']['success'] and violation <= settings['maximum_primal_violation']
            and predicted > 0 and actual > 0 and ratio >= settings['acceptance_ratio'])
        row = dict(iteration=iteration, radius=radius, before_cost=before, candidate_cost=cost,
            predicted_reduction=predicted, actual_reduction=actual, ratio=ratio, accepted=accepted,
            original_parameter_violation=violation, scaled_step_maximum=float(abs(step).max()),
            candidate_parameters=candidate.tolist(), subproblem=result)
        history.append(row)
        if progress:
            progress(row)
        if not result['certificate']['success']:
            break
        if accepted:
            x = candidate
        if not accepted or ratio < .25:
            radius *= .25
        elif ratio > .75 and abs(step).max() > .8*radius:
            radius = min(2*radius, settings['maximum_radius'])
        if radius < settings['minimum_radius']:
            break
    return x, dict(history=history, scales=scales.tolist(), initial_cost=initial_cost,
        final_cost=float(.5*np.sum((model.samples(x)-target)**2)), final_radius=radius,
        iterations=len(history), accepted_steps=sum(row['accepted'] for row in history),
        every_subproblem_certified=all(row['subproblem']['certificate']['success'] for row in history),
        convergence='Finite trust-region budget; no nonlinear or global convergence claim')
