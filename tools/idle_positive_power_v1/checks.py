"""Known positive source laws and numerical contracts before real recordings."""
import numpy as np
from idle_phase_difference_v1.features import matrix
from .model import fit, predict, average, bounds, objective


def run():
    t = np.arange(48000)/48000
    frequency = np.array([71.3, 119.7, 203.1]); phase = np.array([.2, -.6, 1.1])
    z = np.exp(1j*(2*np.pi*t[:, None]*frequency+phase))
    f = matrix(z, hop=1, trim=0)
    coefficient = np.zeros((13, 4)); coefficient[0] = [.1, -.2, .2, -.1]
    coefficient[1:7] = np.array([[.07, -.05, .1, .03], [-.04, .05, .03, -.06], [.02, -.03, .03, .04],
                                 [.2, -.3, .23, .11], [-.13, .08, .04, .09], [.06, .12, -.14, -.1]])
    coefficient[7:13] = .03
    power = np.exp(coefficient[0]+f@coefficient[1:])
    model = fit(f, power)
    expected = coefficient.copy(); expected[0] -= np.log(power.mean(axis=0))
    error = float(abs(np.asarray(model['coefficients'])-expected).max())
    assert model['converged'] and model['full_rank'] and error < 1e-7
    z2 = np.exp(1j*(2*np.pi*(t[:, None]+2.413)*frequency+phase))
    f2 = matrix(z2, hop=1, trim=0)
    target2 = np.exp(coefficient[0]+f2@coefficient[1:])/power.mean(axis=0)
    prediction_error = float(abs(predict(model, f2)-target2).max())
    assert prediction_error < 1e-7
    rotated = np.exp(1j*np.array([.37, -.29, .63]))
    rotated_model = fit(matrix(z*rotated, hop=1, trim=0), power)
    rotated_prediction = predict(rotated_model, matrix(z2*rotated, hop=1, trim=0))
    rotation_error = float(abs(rotated_prediction-predict(model, f2)).max()); assert rotation_error < 1e-7
    scaled = fit(f, power*.13)
    scale_error = float(abs(np.asarray(scaled['coefficients'])-model['coefficients']).max()); assert scale_error < 1e-7
    # Nonlinear averaging changes the prediction even for a known exact law.
    true_mean = average(power)
    wrong_mean = np.exp(coefficient[0]+average(f)@coefficient[1:])
    jensen_error = float(abs(true_mean-wrong_mean).max()); assert jensen_error > 1e-5
    bound = bounds(coefficient)
    assert np.all(power.min(axis=0) > bound['power_lower']) and np.all(power.max(axis=0) < bound['power_upper'])
    assert bound['finite_normal_bounds']
    native = matrix(z, False, hop=1, trim=0)
    native_coef = np.full((7, 4), .03); native_coef[0] = .1
    native_power = np.exp(native_coef[0]+native@native_coef[1:])
    nested = fit(f, native_power)
    assert nested['converged'] and abs(predict(nested, f)-native_power/native_power.mean(axis=0)).max() < 1e-7
    constant = fit(f, np.ones((len(f), 4)))
    assert constant['converged'] and np.array_equal(np.asarray(constant['coefficients']), np.zeros((13, 4)))
    design = np.column_stack((np.ones(1000), f[:1000])); target = power[:1000, 0]
    b = coefficient[:, 0]*.7
    _, gradient, hessian, _ = objective(design, target, b)
    delta = 1e-5
    basis = np.eye(13)
    numerical_gradient = np.array([(objective(design, target, b+delta*v)[0]-objective(design, target, b-delta*v)[0])/(2*delta) for v in basis])
    numerical_hessian = np.column_stack([(objective(design, target, b+delta*v)[1]-objective(design, target, b-delta*v)[1])/(2*delta) for v in basis])
    grad_error = float(abs(gradient-numerical_gradient).max()); hess_error = float(abs(hessian-numerical_hessian).max())
    assert grad_error < 1e-8 and hess_error < 1e-8
    for bad in [power*-1, np.zeros_like(power), power*np.nan]:
        try:
            fit(f, bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid target accepted')
    return dict(coefficient_error=error, shifted_prediction_error=prediction_error,
                independent_phase_origin_error=rotation_error, scale_error=scale_error,
                jensen_averaging_error=jensen_error, finite_difference_gradient_error=grad_error,
                finite_difference_hessian_error=hess_error, native_nested=True,
                constant_stationary=True, invalid_targets_rejected=True, analytic_positive_bounds=True)
