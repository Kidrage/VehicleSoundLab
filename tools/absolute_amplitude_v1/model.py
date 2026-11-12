"""Equivalent absolute-amplitude/phase blocks for the existing finite-band model."""
import numpy as np
from aperture_model_v1.forward import real_rows
from positive_band_envelope_v1.model import BandModel


class AbsoluteModel:
    def __init__(self, time, plan, variant, selected):
        self.phase_bound = plan['phase_control_bound_cycles']
        self.departure_bound = variant['departure_control_bound_radians']
        self.original = BandModel(time, plan, variant, selected)
        m = self.original
        self.full = np.column_stack((1-m.envelope_basis.sum(axis=1), m.envelope_basis))
        self.parts, self.controls = m.parts, self.full.shape[1]
        self.outer_count = m.parts+m.phase_count+len(selected)*m.departure_count
        self.bound = plan['amplitude_control_bound']

    def unpack(self, parameters):
        m = self.original
        c0 = np.hypot(parameters[:m.parts], parameters[m.parts:2*m.parts])
        angles = np.arctan2(-parameters[m.parts:2*m.parts], parameters[:m.parts])
        first = 2*m.parts+m.phase_count
        beta = parameters[first:m.base_count].reshape(m.parts, m.envelope_count)
        controls = np.column_stack((c0, c0[:, None]*(1+beta)))
        outer = np.r_[angles, parameters[2*m.parts:first], parameters[m.base_count:]]
        return outer, controls

    def pack(self, outer, controls):
        m = self.original
        c0 = controls[:, 0]
        beta = np.divide(controls[:, 1:], c0[:, None], out=np.ones_like(controls[:, 1:]),
            where=c0[:, None] > 0)-1
        return np.r_[c0*np.cos(outer[:m.parts]), -c0*np.sin(outer[:m.parts]),
            outer[m.parts:m.parts+m.phase_count], beta.ravel(), outer[m.parts+m.phase_count:]]

    def caps(self, outer):
        angles = outer[:self.parts]
        # Exactly the original |a|<=1, |b|<=1 coefficient box at these angles.
        return 1/np.maximum(abs(np.cos(angles)), abs(np.sin(angles)))

    def phase_bounds(self, controls, outer):
        m = self.original
        lower = np.full(self.outer_count, -np.inf)
        upper = np.full(self.outer_count, np.inf)
        c0 = controls[:, 0]
        # c0>1 restricts a phase angle to its current feasible quadrant branch.
        active = np.flatnonzero(c0 > 1)
        for k in active:
            angle = outer[k]
            quadrant = np.floor(angle/(np.pi/2))
            margin = np.arccos(np.clip(1/c0[k], 0, 1))
            lower[k] = quadrant*np.pi/2+margin
            upper[k] = (quadrant+1)*np.pi/2-margin
        lower[m.parts:m.parts+m.phase_count] = -self.phase_bound
        upper[m.parts:m.parts+m.phase_count] = self.phase_bound
        lower[m.parts+m.phase_count:] = -self.departure_bound
        upper[m.parts+m.phase_count:] = self.departure_bound
        return lower, upper

    def carrier(self, outer):
        m = self.original
        phase = m.phase_basis@outer[m.parts:m.parts+m.phase_count]
        angle = 2*np.pi*(m.time[:, None]+phase[:, None])*m.orders[None, :]+outer[None, :m.parts]
        first = m.parts+m.phase_count
        for position, index in enumerate(m.selected):
            start = first+position*m.departure_count
            angle[:, index] += m.departure_basis@outer[start:start+m.departure_count]
        return np.cos(angle), np.sin(angle), phase

    def design(self, outer):
        cosine = self.carrier(outer)[0]
        values = (cosine[:, :, None]*self.full[:, None, :]).reshape(len(cosine), -1)
        return real_rows(self.original.aperture.apply(values))

    def prediction(self, outer, controls, jacobian=False):
        m = self.original
        cosine, sine, phase = self.carrier(outer)
        amplitude = self.full@controls.T
        samples = np.sum(amplitude*cosine, axis=1)
        if not jacobian:
            return real_rows(m.aperture.apply(samples))
        slope = -amplitude*sine
        common = (slope*2*np.pi*m.orders).sum(axis=1)
        blocks = [slope, common[:, None]*m.phase_basis]
        blocks.extend(slope[:, k, None]*m.departure_basis for k in m.selected)
        combined = m.aperture.apply(np.column_stack((samples, *blocks)))
        return real_rows(combined[:, 0]), real_rows(combined[:, 1:])
