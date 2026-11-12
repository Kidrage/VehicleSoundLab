"""Migrate the previous observed phase with bounded least squares, no truth input."""
import numpy as np
from scipy.optimize import lsq_linear
from positive_band_envelope_v1.model import BandModel
from .model import QuinticBandModel


def migrate(time, plan, variant, selected, previous):
    old = BandModel(time, plan, variant, selected)
    new = QuinticBandModel(time, plan, variant, selected)
    if not np.array_equal(old.envelope_basis, new.envelope_basis) or not np.array_equal(old.departure_basis, new.departure_basis):
        raise ValueError('Only common phase may change')
    if previous.shape != (old.parameter_count,):
        raise ValueError('Previous actual parameters have the wrong schema')
    result = np.zeros(new.parameter_count)
    count = 2*old.parts
    result[:count] = previous[:count]
    observed_phase = old.phase_basis@previous[count:count+old.phase_count]
    bound = plan['phase_control_bound_cycles']
    fitted = lsq_linear(new.phase_basis, observed_phase, bounds=(-bound, bound), tol=1e-13)
    if not fitted.success:
        raise ArithmeticError('Observed phase migration did not converge')
    result[count:count+new.phase_count] = fitted.x
    old_first, new_first = count+old.phase_count, count+new.phase_count
    result[new_first:new.base_count] = previous[old_first:old.base_count]
    result[new.base_count:] = previous[old.base_count:]
    before, old_phase, old_envelope = old.samples(previous)
    after, new_phase, new_envelope = new.samples(result)
    lower, upper = new.bounds(plan, variant)
    assert np.max(lower-result) <= 1e-10 and np.max(result-upper) <= 1e-10
    assert np.array_equal(old_envelope, new_envelope)
    return result, dict(solver_success=bool(fitted.success), previous_parameters=old.parameter_count,
        new_parameters=new.parameter_count, old_phase_controls=old.phase_count, new_phase_controls=new.phase_count,
        unchanged_knot_cycles=plan['phase_knot_cycles'], coefficients_exact=bool(np.array_equal(result[:count], previous[:count])),
        amplitude_controls_exact=bool(np.array_equal(result[new_first:new.base_count], previous[old_first:old.base_count])),
        minority_controls_exact=bool(np.array_equal(result[new.base_count:], previous[old.base_count:])),
        maximum_phase_migration_error=float(abs(new_phase-old_phase).max()),
        rms_phase_migration_error=float(np.sqrt(np.mean((new_phase-old_phase)**2))),
        maximum_waveform_migration_error=float(abs(after-before).max()),
        exact_migration_claimed=False, truth_used=False, heldout_used=False)
