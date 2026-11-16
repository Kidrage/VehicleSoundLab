"""Compose full objective, original seven target groups and all seventeen metrics."""
import numpy as np
from scipy.linalg import norm
from .source import Source
from .observation import Observation
from .prior import Prior


def ratio(error,target):
    scale=float(norm(np.ravel(target)))
    return float(norm(np.ravel(error))/scale) if scale else (0. if not np.count_nonzero(error) else None)


class System:
    def __init__(self,frames,positions,orders,scale,weights,amplitude,sigma):
        self.source=Source(frames,positions,orders,scale)
        self.observation=Observation(frames,weights,amplitude,sigma);self.prior=Prior(self.source)
        self.size=self.source.size

    def full_forward(self,x):return self.observation.full(self.source.forward(x))
    def full_adjoint(self,y):return self.source.adjoint(self.observation.full_adjoint(y))
    def target_forward(self,x):return self.observation.target(self.source.forward(x))
    def target_adjoint(self,groups):return self.source.adjoint(self.observation.target_adjoint(groups))

    def objective(self,x,audio):
        residual=self.full_forward(x)-self.observation.full(audio)
        return float(.5*residual@residual+self.prior.cost(x))

    def gradient(self,x,audio):return self.full_adjoint(self.full_forward(x)-self.observation.full(audio))+self.prior.apply(x)

    def assess(self,wave,audio):
        error=wave-audio;observer=self.observation
        rows,reference=observer.spectral(error),observer.spectral(audio)
        target_rows,target_reference=rows[observer.target_slots],reference[observer.target_slots]
        metrics=dict(whole_wave_NRMSE=ratio(error,audio),target_wave_NRMSE=ratio(error[2048:-2048],audio[2048:-2048]),
            target_supported_band_complex_NRMSE=[ratio(target_rows[:,observer.bands==g],target_reference[:,observer.bands==g]) for g in range(6)],
            whole_supported_band_complex_NRMSE=[ratio(rows[:,observer.bands==g],reference[:,observer.bands==g]) for g in range(6)],
            whole_wave_regions_NRMSE=[ratio(error[p],audio[p]) for p in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
        required=[metrics['target_wave_NRMSE']]+metrics['target_supported_band_complex_NRMSE']
        return dict(metrics=metrics,original_fidelity_passed=all(v is not None and v<.02 for v in required),
            no_source_statistics_C_or_naturalness_qualification=True)
