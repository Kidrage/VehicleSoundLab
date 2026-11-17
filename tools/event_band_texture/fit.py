"""Finite-waveform response and one bounded training-only fit."""
import numpy as np
from scipy import optimize

from event_authoring.contour_response import QuadraticResponse
from event_authoring.source_support import SupportProblem
from event_authoring.response_fit import EDGES
from .profile import EDGES as TEMPORAL_EDGES, TRAIN_SEEDS, vector, with_vector
from .voice import basis


class Response:
    def __init__(self, profile, seconds, seeds=TRAIN_SEEDS):
        self.count = 32
        self.seeds = tuple(seeds)
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError('Distinct training realizations required')
        temporal, spectral = [], []
        for seed in self.seeds:
            waves = basis(profile, seconds, seed)
            temporal.append(QuadraticResponse._grams(waves, 240, TEMPORAL_EDGES))
            spectral.append(QuadraticResponse._grams(waves, 1024, EDGES).mean(axis=1))
        self.temporal, self.spectral = np.array(temporal), np.array(spectral)


def solve(profile, reference, indices, targets, legacy, seconds, seeds=TRAIN_SEEDS):
    response = Response(profile, seconds, seeds)
    initial = vector(profile)
    problem = SupportProblem(response, initial, reference, indices, targets, legacy)
    result = optimize.minimize(lambda g: problem.evaluate(g)[0], initial,
        jac=lambda g: problem.evaluate(g)[1], method='SLSQP', bounds=[(0., 8.)]*32,
        constraints=[dict(type='ineq', fun=lambda g: problem.evaluate(g)[2],
                          jac=lambda g: problem.evaluate(g)[3])],
        options=dict(maxiter=160, ftol=1e-10))
    candidate = with_vector(profile, np.clip(result.x, 0, 8))
    return candidate, dict(optimizer_terminated=bool(result.success), optimizer_message=str(result.message),
        iterations=int(result.nit), evaluations=int(result.nfev),
        initial_objective=problem.evaluate(initial)[0], objective=problem.evaluate(vector(candidate))[0],
        minimum_constraint=float(np.min(problem.evaluate(vector(candidate))[2])),
        accepted=False, runtime_integrated=False)


class Coordinates:
    """Invertible parameter coordinates, identical objective and feasible profiles."""
    def __init__(self, problem, initial):
        self.problem = problem
        band_scale = np.maximum(np.sqrt(np.mean(np.asarray(initial).reshape(4, 8)**2, axis=1)), 1e-12)
        self.scale = np.repeat(band_scale, 8)

    def evaluate(self, values):
        objective, gradient, constraints, jacobian = self.problem.evaluate(np.asarray(values)*self.scale)
        return objective, gradient*self.scale, constraints, jacobian*self.scale[None, :]


def solve_conditioned(profile, reference, indices, targets, legacy, seconds, seeds=TRAIN_SEEDS):
    response = Response(profile, seconds, seeds)
    initial = vector(profile)
    problem = SupportProblem(response, initial, reference, indices, targets, legacy)
    coordinates = Coordinates(problem, initial)
    result = optimize.minimize(lambda z: coordinates.evaluate(z)[0], initial/coordinates.scale,
        jac=lambda z: coordinates.evaluate(z)[1], method='SLSQP',
        bounds=[(0., float(8/s)) for s in coordinates.scale],
        constraints=[dict(type='ineq', fun=lambda z: coordinates.evaluate(z)[2],
                          jac=lambda z: coordinates.evaluate(z)[3])],
        options=dict(maxiter=160, ftol=1e-10))
    physical = np.clip(result.x*coordinates.scale, 0, 8)
    candidate = with_vector(profile, physical)
    return candidate, dict(optimizer_terminated=bool(result.success), optimizer_message=str(result.message),
        iterations=int(result.nit), evaluations=int(result.nfev),
        initial_objective=problem.evaluate(initial)[0], objective=problem.evaluate(physical)[0],
        minimum_constraint=float(np.min(problem.evaluate(physical)[2])),
        coordinate_scale=coordinates.scale.tolist(), identical_physical_bounds=True,
        accepted=False, runtime_integrated=False)
