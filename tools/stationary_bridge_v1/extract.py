"""Source-window selection and compilation; no physical RPM inference."""
from fractions import Fraction
import numpy as np
from scipy import signal
from exterior_clock_v1.warp import warp, polish, carrier_rows
from sound_dna.windowed import estimate


def targets(roots):
    lower, upper, high = roots
    return [lower*(upper/lower)**(1/3), lower*(upper/lower)**(2/3),
            np.sqrt(upper*high)]


def compile_anchor(audio, source_start, clock, target, plan):
    times = np.array([r['seconds'] for r in clock])
    roots = np.array([r['root_hz'] for r in clock])
    cycles = np.r_[0, np.cumsum(np.diff(times)*(roots[:-1]+roots[1:])/2)]
    center = int(np.argmin(abs(roots-target)))
    lo, hi = cycles[center]+np.array([-.5, .5])*plan['initial_cycles']
    if not cycles[0] <= lo < hi <= cycles[-1]:
        raise ValueError('The chosen acoustic-cycle aperture leaves the frozen clock')
    start, stop = np.interp([lo, hi], cycles, times)
    before, initial_positions, initial = warp(audio, source_start, times, roots, start, stop)
    normalized, positions, phase = polish(audio, source_start, before, initial_positions,
                                          plan['phase_reference'], initial['source_cutoff_hz'])
    base = phase['root_hz_median']
    diagnostics = {}
    for order in plan['heldout_orders']:
        _, values = carrier_rows(normalized, order)
        diagnostics[str(order)] = (abs(values.mean(axis=0))/np.mean(abs(values), axis=0)).tolist()
    model, stats = estimate(normalized, plan['harmonics'], plan['components'])
    ratio = Fraction(46.875/base).limit_denominator(10000)
    reference = signal.resample_poly(normalized, ratio.numerator, ratio.denominator,
                                     axis=0, window=('kaiser', 8.6))
    return model, reference, normalized, positions, dict(target_root_hz=float(target),
        root_hz=base, initial=initial, phase=phase, heldout_coherence=diagnostics,
        statistics=stats, resample_ratio=[ratio.numerator, ratio.denominator],
        source_window_policy='18 observed acoustic cycles, same stereo map, both edges discarded; falling-rev mixture, not a steady RPM/load cell')
