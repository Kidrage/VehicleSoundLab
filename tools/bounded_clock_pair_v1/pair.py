"""Construct finite model pairs without fixture truth or recorded-waveform inputs."""
import numpy as np
from scipy.linalg import solve_triangular


def solve(matrix, target):
    q, r = np.linalg.qr(matrix, mode='reduced')
    if np.any(np.diag(r) == 0):
        raise ArithmeticError('Constant-coefficient design is singular')
    coefficients = solve_triangular(r, q.T@target)
    residual = matrix@coefficients-target
    stationarity = float(abs(matrix.T@residual).max())
    scale = float(max(abs(matrix.T@target).max(), 1e-30))
    return coefficients, dict(method='thin_QR_and_triangular_solve',
        normalized_stationarity=stationarity/scale, absolute_stationarity=stationarity,
        design_condition=float(np.linalg.cond(matrix)), singular_value_truncation=False)


def design(model, parameters):
    m = model.original
    _, phase, envelope = m.samples(parameters)
    angle = 2*np.pi*(m.time[:, None]+phase[:, None])*m.orders[None, :]
    return np.column_stack((envelope*np.cos(angle), envelope*np.sin(angle)))


def construct(model, initial, plan):
    m = model.original
    assert not m.selected and m.parts == 36 and m.parameter_count == 732
    interior = (m.time >= 5)&(m.time < 35)
    gap = round(np.diff(m.orders).min()/plan['observed_order_step'])*plan['observed_order_step']
    target = np.sin(2*np.pi*gap*m.time)
    q, r = np.linalg.qr(m.phase_basis, mode='reduced')
    direction = solve_triangular(r, q.T@target)
    curve = m.phase_basis@direction
    gate = plan['rules']['maximum_point_phase_p95_cycles']
    curve_p95 = np.percentile(abs(curve[interior]-np.median(curve[interior])), 95)
    direction *= 2*gate/curve_p95
    perturbation = m.phase_basis@direction
    base_wave, base_phase, envelope = m.samples(initial)
    phase_slice = slice(2*m.parts, 2*m.parts+m.phase_count)
    rows, saved = [], dict(initial=initial, base_waveform=base_wave, perturbation=perturbation,
                           direction_controls=direction, time=m.time)
    for sign in (-1, 1):
        uncorrected = initial.copy()
        uncorrected[phase_slice] += sign*direction
        before_wave = m.samples(uncorrected)[0]
        matrix = design(model, uncorrected)
        coefficients, certificate = solve(matrix, base_wave)
        parameters = uncorrected.copy()
        parameters[:2*m.parts] = coefficients
        waveform, phase, actual_envelope = m.samples(parameters)
        assert np.array_equal(envelope, actual_envelope)
        original_lower, original_upper = m.bounds(plan, dict(departure_control_bound_radians=model.departure_bound))
        violation = float(max(0., (original_lower-parameters).max(), (parameters-original_upper).max()))
        centered = phase-base_phase
        centered -= np.median(centered[interior])
        row = dict(sign=sign, original_parameter_violation=violation,
            minimum_coordinate_step=float(np.diff(m.time+phase).min()), minimum_envelope=float(envelope.min()),
            phase_difference_p95_cycles=float(np.percentile(abs(centered[interior]), 95)),
            raw_difference_norm_before=float(np.linalg.norm(before_wave-base_wave)),
            raw_difference_norm_after=float(np.linalg.norm(waveform-base_wave)),
            coefficient_certificate=certificate,
            coefficient_maximum_absolute_change=float(abs(coefficients-initial[:2*m.parts]).max()))
        row['feasible'] = bool(violation <= 1e-9 and row['minimum_coordinate_step'] > 0 and row['minimum_envelope'] > 0)
        rows.append(row)
        key = 'minus' if sign < 0 else 'plus'
        saved[key+'_parameters'] = parameters
        saved[key+'_waveform'] = waveform
        saved[key+'_before_waveform'] = before_wave
    return rows, saved, dict(minimum_observed_gap=gap, median_aligned_phase_p95_target_cycles=2*gate,
        original_phase_gate=gate, fixed_envelopes=True, truth_used=False, heldout_used=False,
        recorded_audio_used=False, source_orders_retained=m.parts, nonlinear_estimator_run=False)
