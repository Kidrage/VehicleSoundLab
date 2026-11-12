"""One constrained joint tangent direction; no claim of full variable projection."""
import numpy as np
from scipy.linalg import null_space
from .cone import violation
from .amplitude import cost


def step(model, target, outer, controls, scale):
    design = model.design(outer)
    prediction, derivative = model.prediction(outer, controls, True)
    residual = prediction-target
    n = len(outer)
    matrix = np.column_stack((derivative, design))
    psi = residual/np.sqrt(1+(residual/scale)**2)
    curvature = (1+(residual/scale)**2)**(-1.5)
    weighted = matrix*np.sqrt(curvature)[:, None]
    factors = 1/np.maximum(np.linalg.norm(weighted, axis=0), 1e-30)
    equalities = []
    lower, upper = model.phase_bounds(controls, outer)
    for index in range(n):
        if min(outer[index]-lower[index], upper[index]-outer[index]) < 1e-10:
            row = np.zeros(matrix.shape[1]); row[index] = 1
            equalities.append(row)
    for part in range(model.parts):
        first = n+part*model.controls
        c0 = controls[part, 0]
        if c0 < 1e-10:
            row = np.zeros(matrix.shape[1]); row[first] = 1
            equalities.append(row)
        for j in range(1, model.controls):
            for multiplier in (1-model.bound, 1+model.bound):
                if abs(controls[part, j]-multiplier*c0) < 1e-10:
                    row = np.zeros(matrix.shape[1])
                    row[first+j] = 1; row[first] = -multiplier
                    equalities.append(row)
        for value, d_amplitude, d_angle in ((c0*np.cos(outer[part]), np.cos(outer[part]), -c0*np.sin(outer[part])),
            (c0*np.sin(outer[part]), np.sin(outer[part]), c0*np.cos(outer[part]))):
            if abs(abs(value)-1) < 1e-10:
                row = np.zeros(matrix.shape[1]); row[first] = d_amplitude; row[part] = d_angle
                equalities.append(row)
    if equalities:
        constraints = np.asarray(equalities)
        tangent = null_space(constraints*factors[None, :])
    else:
        constraints = np.empty((0, matrix.shape[1]))
        tangent = np.eye(matrix.shape[1])
    system = (weighted*factors[None, :])@tangent
    right = -psi/np.sqrt(curvature)
    solution, _, rank, singular = np.linalg.lstsq(system, right, rcond=None)
    direction = factors*(tangent@solution)
    analytic = matrix@direction
    # Test the joint waveform differential independently of the normal solve.
    delta = 1e-6/max(1., np.linalg.norm(direction))
    observed = (model.prediction(outer+delta*direction[:n], controls+delta*direction[n:].reshape(controls.shape))
        -model.prediction(outer-delta*direction[:n], controls-delta*direction[n:].reshape(controls.shape)))/(2*delta)
    differential_error = float(np.linalg.norm(observed-analytic)/max(np.linalg.norm(analytic), 1e-30))
    # The joint normal direction may nearly cancel amplitude and phase columns.
    # Independently form the real-sample differential with extended accumulation;
    # retain the poorly resolved ordinary finite difference as diagnostic evidence.
    m = model.original
    cosine, sine, _ = model.carrier(outer)
    amplitude = model.full@controls.T
    amplitude_direction = model.full@direction[n:].reshape(controls.shape).T
    phase_direction = m.phase_basis@direction[m.parts:m.parts+m.phase_count]
    angle_direction = direction[None, :m.parts]+2*np.pi*phase_direction[:, None]*m.orders[None, :]
    first = m.parts+m.phase_count
    for position, index in enumerate(m.selected):
        start = first+position*m.departure_count
        angle_direction[:, index] += m.departure_basis@direction[start:start+m.departure_count]
    sample_identity = np.sum(amplitude_direction.astype(np.longdouble)*cosine
        -amplitude.astype(np.longdouble)*sine*angle_direction, axis=1)
    from aperture_model_v1.forward import real_rows
    independent = real_rows(m.aperture.apply(np.asarray(sample_identity, dtype=float)))
    identity_error = float(np.linalg.norm(independent-analytic)/max(np.linalg.norm(analytic), 1e-30))
    if identity_error > 1e-6:
        raise ArithmeticError(f'Independent sample differential failed: {identity_error}')
    before = cost(residual, scale)
    trials = []
    chosen = None
    m = model.original
    for exponent in range(21):
        amount = 2.**(-exponent)
        candidate_outer = outer+amount*direction[:n]
        candidate_controls = controls+amount*direction[n:].reshape(controls.shape)
        parameters = model.pack(candidate_outer, candidate_controls)
        parameter_lower, parameter_upper = m.bounds(
            dict(amplitude_control_bound=model.bound, phase_control_bound_cycles=model.phase_bound),
            dict(departure_control_bound_radians=model.departure_bound))
        feasible = (violation(candidate_controls, model.bound, model.caps(candidate_outer)) <= 1e-10
            and np.max(parameter_lower-parameters) <= 1e-10 and np.max(parameters-parameter_upper) <= 1e-10)
        objective = cost(model.prediction(candidate_outer, candidate_controls)-target, scale) if feasible else None
        trials.append(dict(amount=amount, feasible=bool(feasible), cost=objective))
        if feasible and objective < before:
            chosen = (candidate_outer, candidate_controls)
            break
    report = dict(active_equalities=len(equalities), tangent_columns=tangent.shape[1], numerical_rank=int(rank),
        scaled_joint_condition=float(singular[0]/max(singular[-1], 1e-30)),
        active_equality_direction_error=float(abs(constraints@direction).max()) if equalities else 0.,
        ordinary_joint_finite_difference_relative_error=differential_error,
        independent_sample_differential_relative_error=identity_error,
        direction_norm=float(np.linalg.norm(direction)), ordinary_finite_difference_step=delta,
        directional_gradient=float(psi@analytic), predicted_linearized_residual_norm=float(np.linalg.norm(residual+analytic)),
        original_residual_norm=float(np.linalg.norm(residual)), initial_cost=before, trials=trials,
        accepted=chosen is not None, truth_used=False, heldout_used=False,
        limits=['Active constraints are held on a local equality face; releases and full optimizer convergence are not established',
            'Joint Gauss-Newton curvature is local and does not prove accurate latent phase or real-engine coverage'])
    return (chosen if chosen is not None else (outer.copy(), controls.copy())), report, direction
