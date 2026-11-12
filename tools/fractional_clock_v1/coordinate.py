"""One wide L/R time coordinate, with source-rate antialias protection."""
import numpy as np
from exterior_clock_v1.warp import render_positions


def render(audio, source_start, positions, cycle, maximum_cutoff):
    frequency = 1/(cycle*np.diff(positions))
    cutoff = min(maximum_cutoff, .38*cycle*float(frequency.min()))
    if cutoff < 14000-1e-6:
        raise ValueError('Declared coordinate cannot retain the required14kHz source bandwidth')
    return render_positions(audio, source_start, positions, cutoff), cutoff


def warp(audio, source_start, times, roots, start, stop, plan):
    if not(times[0]<=start<stop<=times[-1]):
        raise ValueError('No extrapolation outside measured coarse observations')
    grid = np.arange(round(start*48000), round(stop*48000)+1)/48000
    hz = np.interp(grid, times, roots)
    phase = np.r_[0, np.cumsum((hz[1:]+hz[:-1])/(2*48000))]
    cycle = plan['samples_per_coarse_cycle']
    positions = np.interp(np.arange(int(phase[-1]*cycle))/cycle, phase, grid)
    normalized, cutoff = render(audio, source_start, positions, cycle, plan['source_lowpass_hz'])
    return normalized, positions, cutoff
