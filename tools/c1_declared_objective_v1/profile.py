"""Original-target calibration and explicit finite-frame geometry independently."""
import numpy as np
from locked_source_guard_v1.measurement import frame


def calibrate(audio):
    rows, coverage = frame(audio)
    starts = np.arange(-3840, len(audio), 256)
    keep = (starts>=0)&(starts+4096<=len(audio))
    amplitude = float(np.sqrt(len(audio)/(256*keep.sum())))
    supported = rows[keep]*amplitude
    groups = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
    power = np.array([np.sum(supported[:, groups==b].real**2+supported[:, groups==b].imag**2)/audio.size for b in range(6)])
    global_power = float(np.mean(audio**2))
    weights = np.ones(2049) if global_power == 0 else 1/np.sqrt(np.maximum(power[groups], global_power*1e-8))
    return dict(weights=weights, band_power=power, floor_active=power<global_power*1e-8,
        sigma=np.sqrt(global_power) if global_power else 1., amplitude=amplitude,
        global_power=global_power, keep=keep, full_coverage=coverage)


def prepare(d, check):
    old = calibrate(d['metric_target'])
    for key in ('weights', 'band_power', 'sigma', 'amplitude'):
        check('calibration_'+key, d[key], old[key])
    assert np.array_equal(d['floor_active'], old['floor_active']), 'calibration_floor_active'
    rows, coverage = frame(d['audio'])
    starts = np.arange(-3840, len(d['audio']), 256)
    keep = (starts>=0)&(starts+4096<=len(d['audio']))
    supported = np.zeros(len(d['audio']))
    w = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    for first in starts[keep]: supported[first:first+4096] += w*w
    # Frozen legacy calibration remains the actual mathematical objective.
    # The independently recomputed values above verify it, never replace it.
    profile = dict(weights=d['weights'].copy(), sigma=float(d['sigma']), amplitude=float(d['amplitude']),
        rows=rows[keep]*float(d['amplitude']), full_coverage=coverage, keep=keep,
        time_coverage=float(d['amplitude'])**2*supported/coverage)
    return profile, old
