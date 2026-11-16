"""Retain the qualified full objective; never recalibrate it on new audio."""
import numpy as np
from locked_source_fit_v1.adapter import build as original_build


def build(packet):
    z = packet
    system, shared, reference = original_build(z['audio'], z['target'], z['metric_target'],
        z['original_positions'], z['orders'], z['scale'])
    if not np.array_equal(system.synthesis.positions, z['positions']):
        raise ValueError('Original full synthesis node geometry changed')
    for name in ('weights', 'band_power', 'floor_active'):
        if not np.array_equal(getattr(system.metric, name), z[name]):
            raise ValueError('Legacy calibration mismatch: '+name)
    if (float(z['sigma']) != system.metric.wave_scale or float(z['amplitude']) != system.metric.amplitude_scale):
        raise ValueError('Legacy waveform/amplitude calibration changed')
    return system, shared, reference
