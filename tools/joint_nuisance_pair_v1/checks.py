"""Independent scalar waveforms, finite-difference derivatives and known fitted controls."""
import math
import numpy as np
from .model import FixedClockModel
from .fit import fit


def check(settings):
    time = np.arange(256)/128
    angle = 2*np.pi*time[:, None]*np.array([1., 2.])[None, :]
    basis = (.5+.25*np.cos(2*np.pi*time))[:, None]
    model = FixedClockModel(np.cos(angle), np.sin(angle), basis, .25)
    x = np.array([.4, .2, -.15, .1, .12, -.18])
    values, derivative = model.samples(x, True)
    scalar = np.array([math.fsum((1+float(basis[k, 0])*x[4+j])*(math.cos(float(angle[k, j]))*x[j]+
        math.sin(float(angle[k, j]))*x[j+2]) for j in range(2)) for k in range(len(time))])
    waveform_error = float(abs(values-scalar).max())
    columns = []
    delta = np.finfo(float).eps**(1/3)
    for j in range(len(x)):
        direction = np.eye(len(x))[j]*delta
        columns.append((model.samples(x+direction)-model.samples(x-direction))/(2*delta))
    numerical = np.column_stack(columns)
    derivative_error = float(np.linalg.norm(numerical-derivative)/np.linalg.norm(derivative))
    assert waveform_error <= 1e-12 and derivative_error <= 1e-6
    cases = []
    specs = [
        ('orthogonal_interior', np.zeros((len(time), 0)), np.array([.4, -.2]), np.array([.4, -.2])),
        ('orthogonal_coefficient_bounds', np.zeros((len(time), 0)), np.array([1.3, -1.4]), np.array([1., -1.])),
        ('bilinear_phase_envelope', basis, np.array([.42, .18, .08]), np.array([.42, .18, .08]))]
    for name, envelope, truth, expected in specs:
        small = FixedClockModel(np.cos(angle[:, :1]), np.sin(angle[:, :1]), envelope, .25)
        initial = np.array([.4, .2, .1]) if envelope.shape[1] else np.zeros(2)
        target = small.samples(truth)
        parameters, result = fit(small, target, initial, settings)
        error = float(abs(parameters-expected).max())
        passed = bool(error <= 1e-7 and result['every_subproblem_certified'])
        cases.append(dict(id=name, passed=passed, maximum_parameter_error=error,
            initial_parameters=initial.tolist(), final_parameters=parameters.tolist(), fit=result))
    return dict(passed=all(row['passed'] for row in cases), scalar_waveform_error=waveform_error,
        central_difference_relative_error=derivative_error, cases=cases,
        known_control_only=True, phase_estimator_qualified=False)
