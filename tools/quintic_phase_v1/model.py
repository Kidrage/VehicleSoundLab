"""Replace common phase only; inherit all existing waveform/parameter equations."""
import numpy as np
from positive_band_envelope_v1.model import BandModel
from absolute_amplitude_v1.model import AbsoluteModel
from .basis import basis


class QuinticBandModel(BandModel):
    def __init__(self, time, plan, variant, selected):
        super().__init__(time, plan, variant, selected)
        self.phase_basis = basis(time, plan['cycles'], plan['phase_knot_cycles'])
        self.phase_count = self.phase_basis.shape[1]
        self.base_count = 2*self.parts+self.phase_count+self.parts*self.envelope_count
        self.parameter_count = self.base_count+len(selected)*self.departure_count


class QuinticAbsoluteModel(AbsoluteModel):
    def __init__(self, time, plan, variant, selected):
        self.phase_bound = plan['phase_control_bound_cycles']
        self.departure_bound = variant['departure_control_bound_radians']
        self.original = QuinticBandModel(time, plan, variant, selected)
        m = self.original
        self.full = np.column_stack((1-m.envelope_basis.sum(axis=1), m.envelope_basis))
        self.parts, self.controls = m.parts, self.full.shape[1]
        self.outer_count = m.parts+m.phase_count+len(selected)*m.departure_count
        self.bound = plan['amplitude_control_bound']
