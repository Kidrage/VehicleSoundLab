"""Nominal phase-grid safeguards; no strict nonlinear bandwidth theorem."""
import numpy as np


def describe(clock, orders, taps, cutoff_hz, native_rate=48000):
    taps = np.asarray(taps)
    if (native_rate != 48000 or not np.isfinite(cutoff_hz) or not 0 < cutoff_hz < native_rate/2
            or taps.ndim != 1 or len(taps) < 3 or len(taps)%2 != 1 or np.iscomplexobj(taps)
            or not np.isfinite(taps).all() or not np.array_equal(taps, taps[::-1])
            or abs(float(taps.sum())-1) > 2e-12):
        raise ValueError('Declared48k source and finite normalized symmetric odd source-FIR required')
    c, h = clock['coefficients'], np.diff(clock['x'])
    candidates = [c[2], (3*c[0]*h+2*c[1])*h+c[2]]
    at = np.divide(-c[1], 3*c[0], out=np.zeros_like(h), where=c[0]!=0)
    valid = (c[0]!=0)&(at>0)&(at<h)
    interior = (3*c[0]*at+2*c[1])*at+c[2]
    minimum = min(float(np.min(v)) for v in candidates)
    maximum = max(float(np.max(v)) for v in candidates)
    if np.any(valid):
        minimum = min(minimum, float(np.min(interior[valid])))
        maximum = max(maximum, float(np.max(interior[valid])))
    if not 0 < minimum <= maximum or not np.isfinite(maximum):
        raise ValueError('Every clock interval requires positive finite derivative')
    low_rate, high_rate = 1/maximum, 1/minimum
    if cutoff_hz > .4*low_rate:
        raise ValueError('Nominal source cutoff exceeds the slowest phase-grid sampling safeguard')
    root = [low_rate/1024, high_rate/1024]
    return dict(native_rate_Hz=native_rate, native_Nyquist_Hz=native_rate/2,
        declared_source_FIR_nominal_cutoff_Hz=float(cutoff_hz), source_FIR_taps=len(taps),
        derivative_seconds_per_virtual_sample=[minimum, maximum],
        phase_grid_samples_per_source_second=[low_rate, high_rate], acoustic_root_Hz=root,
        phase_grid_Nyquist_Hz=[low_rate/2, high_rate/2], nominal_grid_guard_Hz=.4*low_rate,
        highest_retained_order=int(np.max(orders)),
        highest_carrier_centre_Hz=[float(np.max(orders))*v for v in root],
        carrier_centre_is_not_strict_bandwidth=True, finite_FIR_is_not_brickwall=True,
        strict_alias_free_proof=False, actual_crank_RPM_identified=False,
        raw_fullband_preserved=False, physical_source_separation=False)
