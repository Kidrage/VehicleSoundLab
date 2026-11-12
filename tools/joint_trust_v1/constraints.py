"""Convex joint subproblem projection, with Dykstra primal/dual diagnostics."""
import numpy as np
from absolute_amplitude_v1.cone import project as cone_project, violation


class Region:
    def __init__(self, model, outer, controls, scales, radius, settings):
        self.model, self.outer, self.controls = model, outer.copy(), controls.copy()
        self.n, self.scales, self.radius = len(outer), scales.copy(), radius
        self.settings = settings
        self.base = np.r_[outer, controls.ravel()]
        m = model.original
        lower = np.full_like(self.base, -np.inf)
        upper = np.full_like(self.base, np.inf)
        lower[m.parts:m.parts+m.phase_count] = -model.phase_bound
        upper[m.parts:m.parts+m.phase_count] = model.phase_bound
        lower[m.parts+m.phase_count:self.n] = -model.departure_bound
        upper[m.parts+m.phase_count:self.n] = model.departure_bound
        self.lower = np.maximum((lower-self.base)/scales, -radius)
        self.upper = np.minimum((upper-self.base)/scales, radius)
        if np.any(self.lower > self.upper):
            raise ValueError('Empty original phase/trust intersection')
        self.amplitude_scales = scales[self.n:].reshape(controls.shape)
        if not np.all(self.amplitude_scales == self.amplitude_scales[:, :1]):
            raise ValueError('Amplitude scale must be constant within each cone')
        self.first = self.n+np.arange(model.parts)*model.controls
        phi, c0 = outer[:model.parts], controls[:, 0]
        self.planes = []
        for a, b, value in ((np.cos(phi), -c0*np.sin(phi), c0*np.cos(phi)),
            (np.sin(phi), c0*np.cos(phi), c0*np.sin(phi))):
            for sign in (-1, 1):
                self.planes.append((sign*a*scales[self.first],
                    sign*b*scales[:model.parts], 1-sign*value))

    def cone(self, value):
        result = value.copy()
        absolute = self.controls+self.amplitude_scales*value[self.n:].reshape(self.controls.shape)
        projected = cone_project(absolute, self.model.bound, np.sqrt(2.))
        result[self.n:] = ((projected-self.controls)/self.amplitude_scales).ravel()
        return result

    def plane(self, value, plane):
        a, b, limit = plane
        result = value.copy()
        dot = a*value[self.first]+b*value[:self.model.parts]
        denominator = a*a+b*b
        correction = np.maximum(dot-limit, 0)/np.maximum(denominator, 1e-30)
        result[self.first] -= correction*a
        result[:self.model.parts] -= correction*b
        return result

    def violation(self, value):
        absolute = self.controls+self.amplitude_scales*value[self.n:].reshape(self.controls.shape)
        errors = [0., np.max(self.lower-value), np.max(value-self.upper),
            violation(absolute, self.model.bound, np.sqrt(2.))]
        errors.extend(np.max(a*value[self.first]+b*value[:self.model.parts]-limit)
            for a, b, limit in self.planes)
        return float(max(errors))

    def project(self, value):
        actions = [self.cone, lambda x: np.clip(x, self.lower, self.upper)]
        actions.extend(lambda x, plane=p: self.plane(x, plane) for p in self.planes)
        corrections = [np.zeros_like(value) for _ in actions]
        points = [value.copy() for _ in actions]
        result = value.copy()
        success = False
        for iteration in range(1, self.settings['projection_iterations']+1):
            previous = result.copy()
            for k, action in enumerate(actions):
                shifted = result+corrections[k]
                result = action(shifted)
                corrections[k] = shifted-result
                points[k] = result.copy()
            movement = float(abs(result-previous).max())
            error = self.violation(result)
            # Every correction is normal to its set at its last projected point.
            # value-result=sum(corrections), yielding this projection dual gap.
            gap = float(sum(np.dot(p, z-result) for p, z in zip(corrections, points)))
            invariant = float(abs(value-result-sum(corrections)).max())
            tolerance = self.settings['projection_tolerance']
            if error <= tolerance and movement <= tolerance and abs(gap) <= tolerance*max(1., np.dot(value, value)):
                success = True
                break
        return result, dict(success=success, iterations=iteration, constraint_violation=error,
            projection_dual_gap=gap, correction_invariant_error=invariant, last_movement=movement)

    def retract(self, value):
        candidate = self.base+self.scales*value
        outer = candidate[:self.n].copy()
        controls = candidate[self.n:].reshape(self.controls.shape).copy()
        caps = self.model.caps(outer)
        before_projection = controls.copy()
        factor = np.minimum(1., caps/np.maximum(controls[:, 0], 1e-30))
        controls *= factor[:, None]
        controls = cone_project(controls, self.model.bound, caps)
        exact = np.r_[outer, controls.ravel()]
        step = (exact-self.base)/self.scales
        cone_error = violation(controls, self.model.bound, caps)
        m = self.model.original
        packed = self.model.pack(outer, controls)
        low, high = m.bounds(dict(amplitude_control_bound=self.model.bound,
            phase_control_bound_cycles=self.model.phase_bound),
            dict(departure_control_bound_radians=self.model.departure_bound))
        original_error = float(max(0., np.max(low-packed), np.max(packed-high)))
        trust_error = float(max(0., np.max(abs(step))-self.radius))
        feasible = max(cone_error, original_error, trust_error) <= 1e-9
        return outer, controls, step, dict(feasible=bool(feasible), amplitude_cone_error=cone_error,
            original_parameter_error=original_error, trust_region_error=trust_error,
            maximum_amplitude_retraction=float(np.max(1-factor)),
            maximum_amplitude_projection_correction=float(abs(controls-before_projection).max()))
