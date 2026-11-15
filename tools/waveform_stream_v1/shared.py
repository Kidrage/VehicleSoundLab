"""Conditions for sharing geometry without merging L/R observations."""
import numpy as np
from observer_complete_v1.synthesis import WaveSynthesis
from observer_supported_v1.fit import SupportedSystem
from observer_supported_v1.metric import SupportedMetric
from observer_inverse_v1.fit import real_vector, complex_array
from waveform_structured_v1.penalty import TemporalPenalty
from waveform_representer_v1.metric import supported_gram


def require_common_metrics(metrics):
    """Channel metrics must carry exactly the same finite objective.

    Re-estimating one SupportedMetric per side generally changes the objective.
    Frame channel counts may differ; time geometry and every scale must agree.
    """
    if not metrics or any(type(m) is not SupportedMetric for m in metrics):
        raise ValueError('Actual SupportedMetric contracts required')
    reference = metrics[0]
    for other in metrics[1:]:
        for name in ('wave_scale', 'amplitude_scale', 'root_hz'):
            if getattr(reference, name) != getattr(other, name):
                raise ValueError('Different per-channel metric '+name)
        for name in ('weights', 'keep'):
            if not np.array_equal(getattr(reference, name), getattr(other, name)):
                raise ValueError('Different per-channel metric '+name)
        for name in ('frames', 'starts', 'window', 'coverage'):
            if not np.array_equal(getattr(reference.frame, name), getattr(other.frame, name)):
                raise ValueError('Different per-channel frame '+name)
    return reference


def require_common_scales(scales):
    reference = np.asarray(scales[0], float)
    if any(not np.array_equal(reference, np.asarray(s, float)) for s in scales[1:]):
        raise ValueError('Different per-channel source scales')
    return reference


class SharedSupportedGeometry:
    """The actual stereo SupportedSystem as one mono operator and two RHS.

    SupportedSystem/WaveSynthesis and TemporalPenalty have channel-diagonal
    operators; their public types and shared parameters are checked explicitly.
    The original stereo system is still used for complete objective/adjoint
    qualification. This class never recomputes side-specific metric weights.
    """
    def __init__(self, system, *, channel_metrics=None, channel_scales=None):
        if type(system) is not SupportedSystem or type(system.synthesis) is not WaveSynthesis:
            raise ValueError('Only the declared channel-independent system is supported')
        C = system.synthesis.channels
        if C not in (1, 2):
            raise ValueError('Expected mono or stereo')
        metrics = [system.metric]*C if channel_metrics is None else list(channel_metrics)
        scales = [system.scale]*C if channel_scales is None else list(channel_scales)
        if len(metrics) != C or len(scales) != C:
            raise ValueError('One metric/scale contract is required per channel')
        self.metric = require_common_metrics([system.metric]+metrics)
        self.scale = require_common_scales([system.scale]+scales)
        if self.metric.wave_scale != system.wave_scale:
            raise ValueError('Metric/system waveform scales differ')
        s = system.synthesis
        self.synthesis = WaveSynthesis(s.frames, s.positions, s.orders, 1)
        self.prior = TemporalPenalty(self.synthesis.shape, system.D.toarray(), system.alpha, system.beta)
        self.channels = C
        self.original = system

    def forward(self, x):
        nodes = complex_array(x, self.synthesis.shape)*self.scale[None]
        return self.synthesis.synthesize(nodes).ravel()

    def adjoint(self, y):
        return real_vector(self.synthesis.adjoint(np.asarray(y)[:, None])*self.scale[None])

    def metric_matrix(self):
        # Uses shared L/R weights and GLOBAL stereo scale from the original
        # metric. No averaging of waveform samples or fitted coefficients.
        return supported_gram(self.metric, order='F')

    def interleave(self, columns):
        columns = np.asarray(columns)
        if columns.shape != (self.prior.size, self.channels):
            raise ValueError('Independent channel coefficient dimensions differ')
        return columns.ravel()
