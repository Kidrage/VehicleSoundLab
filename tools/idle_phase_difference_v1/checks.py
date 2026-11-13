"""Qualified coordinate algebra and counterexamples, before source observations."""
import numpy as np
from idle_conditioned_detail_v1.features import phases
from .features import matrix, PAIRS
from .model import fit, assess, predict
from .budget import decompose


def run():
    rate, n = 48000, 144000
    t = np.arange(n)/rate
    frequencies = np.array([75.17, 112.61, 187.73])
    offset = np.array([.2, -.6, 1.1])
    z = np.exp(1j*(2*np.pi*t[:, None]*frequencies+offset))
    f = matrix(z)
    df = np.array([frequencies[j]-frequencies[i] for i, j in PAIRS])
    dp = np.array([offset[j]-offset[i] for i, j in PAIRS])
    all_f, all_p = np.r_[frequencies, df], np.r_[offset, dp]
    center = (12000+np.arange(2500)*48+23.5)/rate
    truth = np.exp(1j*(2*np.pi*center[:, None]*all_f+all_p))
    truth *= np.sinc(48*all_f/rate)/np.sinc(all_f/rate)
    feature_error = float(abs(f-np.column_stack((truth.real, truth.imag))).max())
    assert feature_error < 1e-11
    coefficient = np.zeros((13, 4)); coefficient[0] = [1., .8, 1.2, .9]
    coefficient[4:7] = [[.14, -.12, .09, .1], [-.08, .04, .11, .03], [.06, .07, -.1, -.08]]
    coefficient[10:13] = [[.03, -.05, .06, .05], [.02, .02, -.04, .01], [-.03, .04, .02, .06]]
    power = np.column_stack((np.ones(len(f)), f)) @ coefficient
    expanded, native = fit(f, power), fit(matrix(z, False), power)
    expected = coefficient/power.mean(axis=0)
    coefficient_error = float(abs(np.asarray(expanded['coefficients'])-expected).max())
    assert expanded['positive_sufficient_bound'] and expanded['full_rank'] and coefficient_error < 1e-11
    z2 = np.exp(1j*(2*np.pi*(t[:, None]+3.123)*frequencies+offset))
    f2 = matrix(z2); p2 = np.column_stack((np.ones(len(f2)), f2)) @ coefficient
    check = assess(expanded, f2, p2)
    assert max(check['mse']) < 1e-23
    assert min(assess(native, matrix(z2, False), p2)['mse']) > 1e-5
    # Independent phase origins rotate differences consistently, preserving predictions.
    rotations = np.exp(1j*np.array([.37, -.29, .63]))
    rotated = fit(matrix(z*rotations), power)
    rotation_error = float(abs(predict(rotated, matrix(z2*rotations))-predict(expanded, f2)).max())
    assert rotation_error < 1e-11
    assert abs(np.asarray(fit(f, power*.13)['coefficients'])-expanded['coefficients']).max() < 1e-11
    native_coef = coefficient.copy(); native_coef[4:7] = native_coef[10:13] = 0
    native_coef[1:4] = .04
    nested_power = np.column_stack((np.ones(len(f)), f)) @ native_coef
    assert max(assess(fit(f, nested_power), f2,
        np.column_stack((np.ones(len(f2)), f2)) @ native_coef)['mse']) < 1e-23
    # Conservative radius cannot exploit dependence: 1+.7cos(theta)-.7cos(theta)=1.
    dependent_lower = 1-abs(.7)-abs(-.7)
    actual_dependent = 1+.7*z[:, 0].real-.7*z[:, 0].real
    assert dependent_lower < 0 and actual_dependent.min() > .999999999
    negative_coef = np.zeros((13, 4)); negative_coef[0] = 1; negative_coef[1] = 1.2
    invalid = fit(f, np.column_stack((np.ones(len(f)), f)) @ negative_coef)
    assert not invalid['positive_sufficient_bound']
    phase_checks = []
    for chirp in [0., .3]:
        true_z = np.exp(1j*(2*np.pi*(t[:, None]*frequencies+.5*chirp*t[:, None]**2)+offset))
        audio = true_z.real @ np.array([.1, .08, .06]) + .01*np.cos(2*np.pi*284.77*t)
        observed = phases(audio, frequencies)
        differences = np.column_stack([observed[:, j]*observed[:, i].conj() for i, j in PAIRS])
        reference = np.column_stack([true_z[:, j]*true_z[:, i].conj() for i, j in PAIRS])
        error = float(np.quantile(abs(np.angle(differences[12000:-12000]/reference[12000:-12000])), .95))
        assert error < .07
        phase_checks.append(dict(chirp_hz_per_second=chirp, difference_phase_p95_radians=error))
    rng = np.random.default_rng(71209)
    target = rng.normal(size=(300, 4))
    predicted = target*.3 + np.roll(target, 2, axis=0)*.2
    terms, stats = decompose(target, predicted, target.std(axis=0), np.arange(-40, 41))
    assert stats['maximum_closure_error'] < 1e-12
    assert abs(terms['PR']-terms['RP']).max() > .01
    return dict(feature_error=feature_error, coefficient_error=coefficient_error,
                shifted_check_mse=check['mse'], phase_rotation_error=rotation_error,
                native_nested=True, scale_invariance=True, negative_bound_detected=True,
                dependent_phase_positive_despite_negative_bound=True,
                actual_low_observer=phase_checks, exact_lag_budget=stats)
