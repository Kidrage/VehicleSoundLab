"""Reuse the original common/minority phase equations with finite-band amplitudes."""
from minority_phase_v1.model import MinorityModel
from .basis import basis


class BandModel(MinorityModel):
    def __init__(self,time,plan,variant,selected):
        super().__init__(time,plan,variant,selected)
        self.envelope_basis,self.band_evidence=basis(time,plan['cycles'],self.orders)
        self.envelope_count=self.envelope_basis.shape[1]
        self.base_count=2*self.parts+self.phase_count+self.parts*self.envelope_count
        self.parameter_count=self.base_count+len(selected)*self.departure_count
