"""Gauge/bounds, unchanged minority law, independent quadrature and derivatives."""
import numpy as np
from positive_band_envelope_v1.model import BandModel
from .model import QuinticBandModel, QuinticAbsoluteModel
from .initialize import migrate


def controls(time, plan, variant, actual_previous):
    rng = np.random.default_rng(851204)
    model = QuinticBandModel(time, plan, variant, [1])
    old = BandModel(time, plan, variant, [1])
    assert model.phase_count == old.phase_count+2
    assert np.array_equal(model.departure_basis, old.departure_basis)
    assert np.array_equal(model.envelope_basis, old.envelope_basis)
    assert abs(model.phase_basis[0]).max() == 0
    random_controls = rng.uniform(-plan['phase_control_bound_cycles'], plan['phase_control_bound_cycles'], model.phase_count)
    common = model.phase_basis@random_controls
    assert abs(common).max() <= plan['phase_control_bound_cycles']+1e-12
    parameters = np.zeros(model.parameter_count)
    parameters[:2*model.parts] = rng.normal(0, .025, 2*model.parts)
    first = 2*model.parts+model.phase_count
    parameters[2*model.parts:first] = rng.normal(0, .003, model.phase_count)
    parameters[first:model.base_count] = rng.uniform(-.1, .1, model.parts*model.envelope_count)
    parameters[model.base_count:] = rng.normal(0, .02, model.departure_count)
    predicted, jacobian = model.prediction(parameters, True)
    derivatives = []
    for label, index in [('common_phase', 2*model.parts+31), ('amplitude', first+4),
        ('minority_phase', model.base_count+5)]:
        direction = np.zeros(model.parameter_count); direction[index] = 1
        step = 1e-6
        observed = (model.prediction(parameters+step*direction)-model.prediction(parameters-step*direction))/(2*step)
        error = float(np.linalg.norm(observed-jacobian[:, index])/np.linalg.norm(jacobian[:, index]))
        assert error < plan['rules']['maximum_jacobian_relative_error']
        derivatives.append(dict(kind=label, relative_error=error))
    # Direct scalar real waveform and global-time quadrature, independent of the
    # inherited sample/Jacobian renderer and FFT/start-rotation convention.
    phase = model.phase_basis@parameters[2*model.parts:first]
    beta = parameters[first:model.base_count].reshape(model.parts, model.envelope_count)
    amplitudes = 1+model.envelope_basis@beta.T
    waveform = np.zeros(len(time))
    for k, order in enumerate(model.orders):
        angle = 2*np.pi*order*(time+phase)
        if k == 1:
            angle += model.departure_basis@parameters[model.base_count:]
        waveform += amplitudes[:, k]*(parameters[k]*np.cos(angle)+parameters[model.parts+k]*np.sin(angle))
    operator = model.aperture
    projection = (predicted[:len(predicted)//2]+1j*predicted[len(predicted)//2:]).reshape(len(operator.starts), -1)
    maximum = 0.
    window = np.sin(np.pi*np.arange(operator.size)/operator.size)**2
    for row in (0, len(operator.starts)//2, len(operator.starts)-1):
        start = operator.starts[row]
        for column in (0, 1, len(operator.orders)//2, len(operator.orders)-1):
            order = operator.orders[column]
            direct = 2*np.sum(waveform[start:start+operator.size]*window
                *np.exp(-2j*np.pi*order*time[start:start+operator.size]))/window.sum()
            maximum = max(maximum, float(abs(direct-projection[row, column])))
    assert maximum < plan['rules']['maximum_forward_check_error']
    absolute_model = QuinticAbsoluteModel(time, plan, variant, [1])
    outer, absolute = absolute_model.unpack(parameters)
    equivalence = float(abs(absolute_model.prediction(outer, absolute)-predicted).max())
    assert equivalence < 1e-12
    # Global cubic polynomials lie in both spaces, so migration should be exact
    # here even though arbitrary piecewise cubic splines are not nested.
    original = np.zeros(old.parameter_count)
    original[:2*old.parts] = parameters[:2*old.parts]
    curve = .01*time/plan['cycles']+.02*(time/plan['cycles'])**2-.003*(time/plan['cycles'])**3
    original[2*old.parts:2*old.parts+old.phase_count] = np.linalg.lstsq(old.phase_basis, curve, rcond=None)[0]
    old_first = 2*old.parts+old.phase_count
    original[old_first:old.base_count] = parameters[first:model.base_count]
    original[old.base_count:] = parameters[model.base_count:]
    transferred, migration = migrate(time, plan, variant, [1], original)
    assert migration['maximum_phase_migration_error'] < 1e-12
    assert migration['maximum_waveform_migration_error'] < 1e-12
    assert migration['minority_controls_exact'] and migration['amplitude_controls_exact']
    actual, observed_migration = migrate(time, plan, variant, [], actual_previous)
    return dict(passed=True, common_phase_controls=model.phase_count, previous_controls=old.phase_count,
        common_phase_origin_exact=True, bounded_partition=True, minority_and_amplitude_bases_exact=True,
        jacobian=derivatives, independent_quadrature_maximum_error=maximum,
        absolute_representation_equivalence=equivalence,
        global_polynomial_migration=migration, actual_observed_migration=observed_migration,
        truth_used=False, heldout_used=False)
