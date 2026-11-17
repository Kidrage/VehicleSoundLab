"""Offline refinement of existing contour gains across fixed excitations.

No contour layout, component, frequency, phase, cutoff or runtime change.  The
affine waveform includes components outside the contours; finite Hann powers
include all cross terms. Held-out realizations never enter the solver.
"""
from copy import deepcopy

import numpy as np
from scipy import optimize

from .contract import validate
from .contour_all_bands import observations
from .contour_response import QuadraticResponse
from .model import synth
from .response_ensemble import TRAIN_SEEDS, HELD_OUT_SEEDS, band_powers, target_powers
from .response_fit import EDGES
from .temporal_fit import band_curves

TEMPORAL_EDGES = ((60, 300), (300, 1200), (1200, 4500), (4500, 14000))


def gains(profile):
    return np.concatenate([c['gain'] for c in profile['contours']]).astype(float)


def with_gains(profile, values):
    result = deepcopy(profile)
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) != sum(len(c['gain']) for c in profile['contours']):
        raise ValueError('Contour gain count differs from existing profile')
    offset = 0
    for c in result['contours']:
        count = len(c['gain'])
        c['gain'] = values[offset:offset+count].tolist()
        offset += count
    return validate(result)


class EnsembleResponse:
    def __init__(self, profile, duration, seeds=TRAIN_SEEDS, retain_waveforms=False):
        validate(profile)
        if not profile.get('contours'):
            raise ValueError('Refinement requires existing contours')
        if not .12 <= duration <= profile['duration_seconds']+1e-12:
            raise ValueError('Invalid material observation duration')
        self.seeds = tuple(seeds)
        if not self.seeds or len(set(self.seeds)) != len(self.seeds) or any(
                type(s) is not int or not 1 <= s <= 4294967295 for s in self.seeds):
            raise ValueError('Fixed excitation seeds must be distinct uint32 values')
        self.count = len(gains(profile))
        zero = with_gains(profile, np.zeros(self.count))
        temporal, spectral, bases = [], [], []
        for seed in self.seeds:
            constant = synth(zero, seed=seed, seconds=duration)
            waves = []
            for index in range(self.count):
                unit = np.zeros(self.count)
                unit[index] = 1.
                waves.append(synth(with_gains(profile, unit), seed=seed, seconds=duration)-constant)
            extended = np.column_stack((*waves, constant))
            temporal.append(QuadraticResponse._grams(extended, 240, TEMPORAL_EDGES))
            spectral.append(QuadraticResponse._grams(extended, 1024, EDGES).mean(axis=1))
            if retain_waveforms:
                bases.append(extended)
        self.temporal = np.array(temporal)
        self.spectral = np.array(spectral)
        self.bases = np.array(bases) if retain_waveforms else None

    def waveform(self, seed_index, values):
        if self.bases is None:
            raise ValueError('Waveforms were not retained')
        return self.bases[seed_index] @ np.r_[values, 1.]


def shape_terms(power, derivative, reference):
    mean = np.maximum(power.mean(axis=-1), 1e-30)
    shape = power/mean[..., None]
    delta = shape-reference
    dshape = derivative/mean[..., None, None] - (
        power[..., None]*derivative.mean(axis=-2)[..., None, :]/mean[..., None, None]**2)
    mse = np.mean(delta**2, axis=-1)
    dmse = 2*np.mean(delta[..., None]*dshape, axis=-2)
    return mse, dmse


class ContourProblem:
    """One SLSQP objective and positive-is-feasible constraints, analytic J."""
    def __init__(self, response, initial, reference, indices, targets):
        self.response = response
        self.indices = list(indices)
        self.reference = reference[self.indices]
        self.targets = np.asarray(targets, dtype=float)
        total = float(self.targets.sum())
        if not self.indices or total <= 1e-20:
            raise ValueError('No reliable temporal band or positive spectral target')
        initial_power = QuadraticResponse.power(response.temporal, initial)[:, self.indices]
        normalized = initial_power/np.maximum(initial_power.mean(axis=-1), 1e-30)[..., None]
        self.baseline_rmse = np.sqrt(np.mean((normalized-self.reference)**2, axis=-1))
        self.weights2 = 1/np.maximum(self.baseline_rmse, .05)**2
        self.shape_limit = (self.baseline_rmse+1e-10)**2
        self.significant = self.targets >= total*1e-4
        self.scale = np.maximum(self.targets, total*1e-4)
        self.upper = np.where(self.significant, self.targets*10**.3,
                              np.maximum(2*self.targets, total*2e-4))
        self.lower = self.targets/10**.3
        self._last = None

    def evaluate(self, values):
        values = np.asarray(values, dtype=float)
        if self._last is not None and np.array_equal(values, self._last[0]):
            return self._last[1]
        response = self.response
        p = QuadraticResponse.power(response.temporal, values)[:, self.indices]
        dp = QuadraticResponse.derivative(response.temporal, values)[:, self.indices]
        mse, dmse = shape_terms(p, dp, self.reference)
        objective = float(np.mean(mse*self.weights2))
        jacobian = np.mean(dmse*self.weights2[..., None], axis=(0, 1))
        power = QuadraticResponse.power(response.spectral, values)
        derivative = QuadraticResponse.derivative(response.spectral, values)
        upper = (self.upper-power)/self.scale
        lower = ((power-self.lower)/self.scale)[:, self.significant]
        shape_scale = np.maximum(self.baseline_rmse**2, .05**2)
        shape = (self.shape_limit-mse)/shape_scale
        constraints = np.r_[upper.ravel(), lower.ravel(), shape.ravel()]
        constraints_jac = np.concatenate((
            (-derivative/self.scale[None, :, None]).reshape(-1, response.count),
            (derivative/self.scale[None, :, None])[:, self.significant].reshape(-1, response.count),
            (-dmse/shape_scale[..., None]).reshape(-1, response.count)))
        result = (objective, jacobian, constraints, constraints_jac)
        self._last = (values.copy(), result)
        return result


def assess(profile, targets, reference, duration, indices, seeds, baselines):
    rows = []
    total = float(targets.sum())
    for seed, baseline in zip(seeds, baselines):
        wave = synth(profile, seed=seed, seconds=duration)
        power = band_powers(wave)
        spectral = []
        for edge, wanted, actual in zip(EDGES, targets, power):
            error = float(10*np.log10(max(actual, 1e-30)/max(wanted, 1e-30)))
            significant = wanted >= total*1e-4
            passed = abs(error) <= 3 if significant else actual <= max(wanted*2, total*2e-4)
            spectral.append(dict(hz=list(edge), target_power=float(wanted), generated_power=float(actual),
                                 error_db=error, passed=bool(passed)))
        _, curve = band_curves(wave)
        normalized = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
        errors = np.sqrt(np.mean((normalized-reference)**2, axis=1))
        temporal_pass = all(errors[i] <= baseline[i]+1e-10 for i in indices)
        rows.append(dict(seed=seed, bands=spectral, shape_rmse=errors.tolist(),
                         baseline_shape_rmse=list(baseline), temporal_nonregression=bool(temporal_pass),
                         qualified=bool(temporal_pass and all(b['passed'] for b in spectral))))
    return rows


def baseline_errors(profile, reference, duration, seeds):
    rows = []
    for seed in seeds:
        _, curve = band_curves(synth(profile, seed=seed, seconds=duration))
        normalized = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
        rows.append(np.sqrt(np.mean((normalized-reference)**2, axis=1)).tolist())
    return rows


def solve(profile, target, band_rows, targets, duration):
    """Exactly one training solve. Call validate_candidate only after saving it."""
    indices = [i for i, row in enumerate(band_rows) if row['selected']]
    reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
    initial = gains(profile)
    response = EnsembleResponse(profile, duration)
    problem = ContourProblem(response, initial, reference, indices, targets)
    before = problem.evaluate(initial)[0]
    result = optimize.minimize(lambda g: problem.evaluate(g)[0], initial,
        jac=lambda g: problem.evaluate(g)[1], method='SLSQP', bounds=[(0., 8.)]*len(initial),
        constraints=[dict(type='ineq', fun=lambda g: problem.evaluate(g)[2],
                          jac=lambda g: problem.evaluate(g)[3])],
        options=dict(maxiter=160, ftol=1e-10))
    # Clip only possible numerical bound overshoot; independently assess saved values.
    candidate = with_gains(profile, np.clip(result.x, 0, 8))
    after = problem.evaluate(gains(candidate))[0]
    improvement = (before-after)/max(before, 1e-30)
    baseline = baseline_errors(profile, reference, duration, TRAIN_SEEDS)
    training = assess(candidate, targets, reference, duration, indices, TRAIN_SEEDS, baseline)
    report = dict(method='existing-contour-ensemble-v1', controls=len(initial),
        training_seeds=list(TRAIN_SEEDS), held_out_seeds=list(HELD_OUT_SEEDS),
        optimizer_terminated=bool(result.success), optimizer_message=str(result.message),
        optimizer_iterations=int(result.nit), evaluations=int(result.nfev),
        objective_before=before, objective_after=after, relative_improvement=improvement,
        useful=bool(improvement > 1e-5), training=training,
        training_qualified=all(row['qualified'] for row in training),
        minimum_predicted_constraint=float(np.min(problem.evaluate(gains(candidate))[2])),
        qualified=False, held_out_evaluated=False,
        policy='One SLSQP solve, max160 iterations, ftol1e-10; existing gains0..8 only. '
               'Four fixed training seeds, original six spectral gates, every reliable band '
               'must retain each seed baseline normalized shape RMSE. No held-out retries.')
    return candidate, report


def validate_candidate(original, candidate, target, band_rows, targets, duration, report):
    """No solve or selection here; caller must freeze the candidate first."""
    indices = [i for i, row in enumerate(band_rows) if row['selected']]
    reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
    baseline = baseline_errors(original, reference, duration, HELD_OUT_SEEDS)
    held = assess(candidate, targets, reference, duration, indices, HELD_OUT_SEEDS, baseline)
    result = deepcopy(report)
    result.update(held_out=held, held_out_evaluated=True,
        qualified=bool(report['useful'] and report['training_qualified'] and all(r['qualified'] for r in held)))
    return result
