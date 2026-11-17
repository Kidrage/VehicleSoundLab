"""Opt-in source-informed support for existing four procedural event bands.

Nominal source groups are not brickwall output bands. Narrower individual SOS
responses reduce cross-control; no physical-source separation is claimed.
"""
from copy import deepcopy

import numpy as np
from scipy import optimize

from .contract import validate
from .contour_all_bands import observations
from .contour_knots import propose
from .contour_response import QuadraticResponse
from .contour_ensemble import (EnsembleResponse, ContourProblem, gains, with_gains,
                               baseline_errors, assess, TEMPORAL_EDGES)
from .model import synth
from .response_ensemble import TRAIN_SEEDS, target_powers, band_powers

HELD_OUT_SEEDS = (19001, 31907, 61979, 91153)


def design(profile, arrays, time, target, rows, duration):
    if len(profile['bands']) != 4 or not all(row['selected'] for row in rows):
        raise ValueError('Source-support design requires four existing noise bands and four reliable source bands')
    f, power, background, *_ = arrays
    excess = np.maximum(power-background, 0)
    result = deepcopy(profile)
    result.pop('noise_lowpass_hz', None)
    result['contours'] = []
    measurements = []
    for index, (low, high) in enumerate(TEMPORAL_EDGES):
        selected = (f >= low)&(f < high)
        hz, weight = f[selected], excess[selected]
        total = float(weight.sum())
        if total <= 1e-20:
            raise ValueError('No positive source support in a reliable band')
        center = float(np.exp(np.sum(weight*np.log(hz))/total))
        cumulative = np.cumsum(weight)/total
        q10, q90 = np.interp([.1, .9], cumulative, hz)
        center = float(np.clip(center, np.nextafter(float(low), float(high)),
                               np.nextafter(float(high), float(low))))
        q = float(np.clip(center/max(q90-q10, 1e-12), 2., 12.))
        band = result['bands'][index]
        band.update(hz=center, q=q)
        seconds = propose(time, target[index], duration)
        shape = np.sqrt(np.maximum(target[index], 0)/max(float(target[index].mean()), 1e-30))
        amplitude = np.clip(np.interp(seconds, time, shape), 0, 8)
        result['contours'].append(dict(low_hz=low, high_hz=high,
                                      seconds=seconds, gain=amplitude.tolist()))
        measurements.append(dict(hz=[low, high], center_hz=center, source_q10_hz=float(q10),
            source_q90_hz=float(q90), source_design_Q=q, seconds=seconds,
            policy='Positive-PSD geometric mean; Q bounded2..12, not a physical resonator estimate'))
    return validate(result), measurements


def noise_basis(profile, duration, seeds=TRAIN_SEEDS):
    constant_profile = deepcopy(profile)
    for b in constant_profile['bands']:
        b['amplitude'] = 0.
    grams = []
    for seed in seeds:
        constant = synth(constant_profile, seed=seed, seconds=duration)
        waves = []
        for index in range(4):
            unit = deepcopy(constant_profile)
            unit['bands'][index]['amplitude'] = 1.
            waves.append(synth(unit, seed=seed, seconds=duration)-constant)
        extended = np.column_stack((*waves, constant))
        from .response_fit import EDGES
        grams.append(QuadraticResponse._grams(extended, 1024, EDGES).mean(axis=1))
    return np.array(grams)


def noise_objective(gram, targets, values):
    floor = float(targets.sum())*1e-6
    power = QuadraticResponse.power(gram, values)
    derivative = QuadraticResponse.derivative(gram, values)
    residual = np.log(np.maximum(power, 0)+floor)-np.log(targets+floor)
    jacobian = derivative/(np.maximum(power, 0)+floor)[..., None]
    return residual.ravel(), jacobian.reshape(-1, len(values))


def calibrate_noise(profile, targets, duration):
    gram = noise_basis(profile, duration)
    initial = np.clip([b['amplitude'] for b in profile['bands']], 0, 8)
    result = optimize.least_squares(lambda a: noise_objective(gram, targets, a)[0], initial,
        jac=lambda a: noise_objective(gram, targets, a)[1], bounds=(0, 8),
        max_nfev=160, ftol=1e-10, xtol=1e-10, gtol=1e-10)
    fitted = deepcopy(profile)
    for b, amplitude in zip(fitted['bands'], result.x):
        b['amplitude'] = float(amplitude)
    return validate(fitted), dict(evaluations=result.nfev, optimizer_terminated=bool(result.success),
        amplitude=result.x.tolist(), residual_log_rmse=float(np.sqrt(np.mean(result.fun**2))),
        policy='One four-amplitude fit across fixed training realizations; modal amplitudes fixed')


class SupportProblem(ContourProblem):
    def __init__(self, response, initial, reference, indices, targets, legacy_errors):
        super().__init__(response, initial, reference, indices, targets)
        self.baseline_rmse = np.asarray(legacy_errors)[:, self.indices]
        self.weights2 = 1/np.maximum(self.baseline_rmse, .05)**2
        self.shape_limit = (self.baseline_rmse+1e-10)**2
        self.upper = np.where(self.significant, self.targets*10**.25, self.upper)
        self.lower = self.targets/10**.25

    def evaluate(self, values):
        objective, jacobian, constraints, cjac = super().evaluate(values)
        power = QuadraticResponse.power(self.response.spectral, values)
        derivative = QuadraticResponse.derivative(self.response.spectral, values)
        floor = float(self.targets.sum())*1e-6
        residual = np.log(np.maximum(power, 0)+floor)-np.log(self.targets+floor)
        gradient = 2*np.mean(residual[..., None]*derivative/(np.maximum(power, 0)+floor)[..., None], axis=(0, 1))
        return objective+float(np.mean(residual**2)), jacobian+gradient, constraints, cjac


def joint_solve(original, profile, target, rows, targets, duration):
    reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
    indices = [i for i, row in enumerate(rows) if row['selected']]
    legacy = baseline_errors(original, reference, duration, TRAIN_SEEDS)
    response = EnsembleResponse(profile, duration)
    initial = gains(profile)
    problem = SupportProblem(response, initial, reference, indices, targets, legacy)
    initial_objective = problem.evaluate(initial)[0]
    solved = optimize.minimize(lambda g: problem.evaluate(g)[0], initial,
        jac=lambda g: problem.evaluate(g)[1], method='SLSQP', bounds=[(0., 8.)]*len(initial),
        constraints=[dict(type='ineq', fun=lambda g: problem.evaluate(g)[2],
                          jac=lambda g: problem.evaluate(g)[3])],
        options=dict(maxiter=160, ftol=1e-10))
    candidate = with_gains(profile, np.clip(solved.x, 0, 8))
    training = assess(candidate, targets, reference, duration, indices, TRAIN_SEEDS, legacy)
    errors = np.array([r['shape_rmse'] for r in training])[:, indices]
    old_errors = np.array(legacy)[:, indices]
    relative_shape_error = float(np.mean((errors/np.maximum(old_errors, .05))**2))
    old_shape_error = float(np.mean((old_errors/np.maximum(old_errors, .05))**2))
    improvement = (old_shape_error-relative_shape_error)/max(old_shape_error, 1e-30)
    report = dict(method='source-support-v1', training=training, training_seeds=list(TRAIN_SEEDS),
        held_out_seeds=list(HELD_OUT_SEEDS), held_out_evaluated=False, qualified=False,
        training_qualified=all(row['qualified'] for row in training),
        controls=len(initial), evaluations=solved.nfev, optimizer_iterations=solved.nit,
        optimizer_terminated=bool(solved.success), optimizer_message=str(solved.message),
        initial_objective=initial_objective, objective=problem.evaluate(gains(candidate))[0],
        relative_legacy_shape_improvement=improvement, useful=bool(improvement > 1e-5),
        minimum_training_constraint=float(np.min(problem.evaluate(gains(candidate))[2])),
        accepted=False, limitations='Four SOS responses are not brickwall-separated sources; '
            'finite-seed acoustic checks do not prove mechanical naturalness, physical parts or RPM.')
    return candidate, report


def fit_training(original, x, background, arrays):
    time, target, rows = observations(x, background)
    targets = target_powers(arrays)
    duration = len(x)/48000
    designed, support = design(original, arrays, time, target, rows, duration)
    calibrated, calibration = calibrate_noise(designed, targets, duration)
    candidate, report = joint_solve(original, calibrated, target, rows, targets, duration)
    report.update(source_support=support, noise_calibration=calibration, bands=rows)
    return candidate, report


def check_held_out(original, candidate, x, background, arrays, report):
    _, target, rows = observations(x, background)
    reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
    indices = [i for i, row in enumerate(rows) if row['selected']]
    targets = target_powers(arrays)
    duration = len(x)/48000
    baseline = baseline_errors(original, reference, duration, HELD_OUT_SEEDS)
    held = assess(candidate, targets, reference, duration, indices, HELD_OUT_SEEDS, baseline)
    result = deepcopy(report)
    result.update(held_out=held, held_out_evaluated=True,
        qualified=bool(report['useful'] and report['training_qualified'] and all(r['qualified'] for r in held)))
    return result
