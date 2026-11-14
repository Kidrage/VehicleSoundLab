"""Fixed source-time apertures; reuse the existing common-stereo warp kernels."""
import numpy as np
from exterior_clock_v1.warp import warp, polish, carrier_rows


def extract(audio, source_start, clock, center_seconds, plan):
    times = np.array([row['seconds'] for row in clock])
    roots = np.array([row['root_hz'] for row in clock])
    if not times[0] <= center_seconds <= times[-1]:
        raise ValueError('The declared center is outside the observed clock')
    cycles = np.r_[0., np.cumsum(np.diff(times)*(roots[1:]+roots[:-1])/2)]
    center_cycle = np.interp(center_seconds, times, cycles)
    lo, hi = center_cycle + np.array([-.5, .5])*plan['aperture_cycles']
    if not cycles[0] <= lo < hi <= cycles[-1]:
        raise ValueError('The fixed aperture leaves the observed clock')
    start, stop = np.interp([lo, hi], cycles, times)
    initial_audio, positions, initial = warp(audio, source_start, times, roots, start, stop)
    normalized, where, phase = polish(audio, source_start, initial_audio, positions,
                                      plan['phase_reference'], initial['source_cutoff_hz'])
    heldout = {}
    for order in plan['heldout_orders']:
        _, rows = carrier_rows(normalized, order)
        heldout[str(order)] = (abs(rows.mean(axis=0))/np.mean(abs(rows), axis=0)).tolist()
    return normalized, where, dict(center_seconds=center_seconds,
        aperture_source_seconds=[float(start), float(stop)], initial=initial, phase=phase,
        root_hz=phase['root_hz_median'], heldout_coherence=heldout)
