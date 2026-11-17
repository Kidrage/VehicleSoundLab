"""Finite response; explicit feasibility phase before one objective solve."""
import numpy as np
from scipy import optimize

from event_authoring.contour_response import QuadraticResponse
from event_authoring.contour_ensemble import TEMPORAL_EDGES
from event_authoring.response_fit import EDGES
from event_authoring.source_support import SupportProblem
from .profile import TRAIN_SEEDS, groups, vector, with_vector
from .voice import basis


class Response:
    def __init__(self, profile, seconds, seeds=TRAIN_SEEDS):
        self.count = len(vector(profile))
        self.seeds = tuple(seeds)
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError('Distinct finite spectral training seeds required')
        temporal, spectral = [], []
        for seed in self.seeds:
            waves = basis(profile, seconds, seed)
            temporal.append(QuadraticResponse._grams(waves, 240, TEMPORAL_EDGES))
            spectral.append(QuadraticResponse._grams(waves, 1024, EDGES).mean(axis=1))
        self.temporal, self.spectral = np.array(temporal), np.array(spectral)


class Coordinates:
    def __init__(self, problem, profile):
        self.problem = problem
        self.scale = np.concatenate([np.full(len(g['gain']), max(float(np.sqrt(np.mean(np.asarray(g['gain'])**2))), 1e-12))
                                     for g in groups(profile)])

    def evaluate(self, values):
        f, gradient, constraints, jacobian = self.problem.evaluate(np.asarray(values)*self.scale)
        return f, gradient*self.scale, constraints, jacobian*self.scale[None, :]


def solve(profile, reference, indices, targets, legacy, seconds, seeds=TRAIN_SEEDS):
    initial = vector(profile)
    response = Response(profile, seconds, seeds)
    problem = SupportProblem(response, initial, reference, indices, targets, legacy)
    coordinate = Coordinates(problem, profile)
    z0 = initial/coordinate.scale
    upper = 8/coordinate.scale
    def feasibility(z):
        return np.maximum(0, .02-coordinate.evaluate(z)[2])
    def feasibility_jac(z):
        _, _, c, j = coordinate.evaluate(z)
        return -j*(c < .02)[:, None]
    phase = optimize.least_squares(feasibility, z0, jac=feasibility_jac, bounds=(0, upper),
        max_nfev=120, ftol=1e-9, xtol=1e-9, gtol=1e-9)
    constraints = coordinate.evaluate(phase.x)[2]
    feasible = bool(np.min(constraints) >= 0)
    report = dict(phaseI=dict(optimizer_terminated=bool(phase.success), evaluations=int(phase.nfev),
        minimum_constraint=float(np.min(constraints)), feasible=feasible),
        phaseII_executed=False, initial_objective=problem.evaluate(initial)[0], accepted=False,
        runtime_integrated=False, controls=len(initial))
    final = phase.x
    if feasible:
        fitted = optimize.minimize(lambda z: coordinate.evaluate(z)[0], phase.x,
            jac=lambda z: coordinate.evaluate(z)[1], method='SLSQP',
            bounds=[(0., float(u)) for u in upper],
            constraints=[dict(type='ineq', fun=lambda z: coordinate.evaluate(z)[2],
                              jac=lambda z: coordinate.evaluate(z)[3])],
            options=dict(maxiter=160, ftol=1e-10))
        final = fitted.x
        report.update(phaseII_executed=True, phaseII=dict(optimizer_terminated=bool(fitted.success),
            message=str(fitted.message), iterations=int(fitted.nit), evaluations=int(fitted.nfev)))
    candidate = with_vector(profile, np.clip(final*coordinate.scale, 0, 8))
    report.update(objective=problem.evaluate(vector(candidate))[0],
                  minimum_constraint=float(np.min(problem.evaluate(vector(candidate))[2])))
    return candidate, report
