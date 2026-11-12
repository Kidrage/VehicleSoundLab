"""Alternate observed absolute-amplitude and phase blocks without oracle access."""
import numpy as np
from scipy.optimize import least_squares
from aperture_model_v1.forward import real_rows
from .model import AbsoluteModel
from .amplitude import solve_amplitudes, cost


def estimate(audio, time, plan, variant, settings, selected, initial, progress=None):
    model = AbsoluteModel(time, plan, variant, selected)
    outer, controls = model.unpack(initial)
    target = real_rows(model.original.aperture.apply(audio[:, 0]))
    initial_prediction = model.prediction(outer, controls)
    history = []
    for cycle in range(settings['outer_cycles']):
        before = cost(model.prediction(outer, controls)-target, plan['soft_l1_scale'])
        design = model.design(outer)
        controls, amplitude = solve_amplitudes(design, target, controls, model.bound,
            model.caps(outer), plan['soft_l1_scale'], settings)
        lower, upper = model.phase_bounds(controls, outer)
        free = upper > lower
        frozen = outer.copy()
        def assemble(x):
            result = frozen.copy()
            result[free] = x
            return result
        cache = {}
        def calculate(x):
            if 'x' not in cache or not np.array_equal(x, cache['x']):
                prediction, jacobian = model.prediction(assemble(x), controls, True)
                cache.update(x=x.copy(), residual=prediction-target, jacobian=jacobian[:, free])
            return cache
        fitted = least_squares(lambda x: calculate(x)['residual'].copy(), outer[free],
            jac=lambda x: calculate(x)['jacobian'].copy(), bounds=(lower[free], upper[free]),
            loss='soft_l1', f_scale=plan['soft_l1_scale'], x_scale='jac',
            max_nfev=settings['phase_evaluations_per_cycle'], ftol=1e-10, xtol=1e-10, gtol=1e-10)
        outer = assemble(fitted.x)
        after = cost(model.prediction(outer, controls)-target, plan['soft_l1_scale'])
        if after > amplitude['cost']+settings['objective_decrease_tolerance']:
            raise ArithmeticError('Phase block increased original robust objective')
        row = dict(cycle=cycle+1, before_cost=before, amplitude=amplitude, after_cost=after,
            phase_success=bool(fitted.success), phase_evaluations=int(fitted.nfev),
            phase_optimality=float(fitted.optimality))
        history.append(row)
        if progress:
            progress(row)
    # Finish on an amplitude solve at the actual final phase, not stale controls.
    controls, final_amplitude = solve_amplitudes(model.design(outer), target, controls, model.bound,
        model.caps(outer), plan['soft_l1_scale'], settings)
    parameters = model.pack(outer, controls)
    samples, phase, envelope = model.original.samples(parameters)
    residual = model.original.prediction(parameters)-target
    amplitude = np.hypot(parameters[:model.parts], parameters[model.parts:2*model.parts])
    remaining = sum(amplitude[k] >= plan['rules']['minimum_carrier_amplitude']
        for k in range(model.parts) if k not in selected)
    normalized = float(np.linalg.norm(residual)/np.linalg.norm(target))
    original_lower, original_upper = model.original.bounds(plan, variant)
    if np.max(original_lower-parameters) > 1e-10 or np.max(parameters-original_upper) > 1e-10:
        raise ArithmeticError('Original parameter bounds violated')
    return parameters, phase, dict(history=history, final_amplitude=final_amplitude,
        initial_cost=cost(initial_prediction-target, plan['soft_l1_scale']), final_cost=cost(residual, plan['soft_l1_scale']),
        normalized_projection_residual=normalized, selected_indices=list(selected),
        remaining_carriers=int(remaining), minimum_envelope=float(envelope.min()), maximum_envelope=float(envelope.max()),
        minimum_coordinate_step=float(np.min(np.diff(time+phase))),
        observation_supported=bool(normalized <= variant['maximum_normalized_projection_residual']
            and remaining >= variant['minimum_remaining_carriers'] and envelope.min() > 0
            and np.min(np.diff(time+phase)) > 0),
        outer_cycles=len(history), solver_success=False,
        convergence='Fixed alternating budget, no joint convergence or global-optimum claim',
        truth_used=False, heldout_used=False, band=model.original.band_evidence)
