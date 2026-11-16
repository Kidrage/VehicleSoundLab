"""Genuine-context physical references for the explicitly new C1 source."""
import numpy as np
from scipy import signal
from clock_c1_v1.geometry import evaluate
from clock_native_bridge_v1.render import render
from locked_source_tail_v1.known import evaluate as analytic


def model(z):
    return {k.removeprefix('clock_'):v for k,v in z.items()
            if k.startswith('clock_') and k != 'clock_times'}


def references(z, *, known):
    clock = model(z)
    # The manufactured target is shorter than one native 4096-point window.
    # Its diagnostic interval uses genuine context, with an explicit margin;
    # actual recordings use precisely the prepared target interval.
    margin = 512 if known else 2048
    first_time, last_time = z['source_coordinates'][[margin, -margin-1]]
    if known:
        first_tick, last_tick = int(np.ceil(first_time*48000)), int(np.floor(last_time*48000))
        start, count = first_tick/48000, last_tick-first_tick+1
        times = start+np.arange(count)/48000
        raw = analytic(times-160., z['source_frequency'], z['source_coefficients'], np.array([1.]))
        filtered = analytic(times-160., z['source_frequency'], z['source_coefficients'], z['source_filter_taps'])
        source = dict(source_frequency=z['source_frequency'], source_coefficients=z['source_coefficients'],
            analytic_origin=np.array(160.))
    else:
        # Align to original recording ticks, retaining the exact source origin.
        origin = float(z['source_start'])
        first = int(np.ceil((first_time-origin)*48000))
        stop = int(np.floor((last_time-origin)*48000))+1
        delay = len(z['source_filter_taps'])//2
        if first-delay < 0 or stop+delay > len(z['native']):
            raise ValueError('Complete original native FIR context required; no padding')
        start, count = origin+first/48000, stop-first
        raw = z['native'][first:stop].copy()
        filtered = signal.convolve(z['native'][first-delay:stop+delay],
            z['source_filter_taps'][:, None], mode='valid', method='direct')
        source = dict(source_native=z['native'], source_start=z['source_start'],
            native_first=np.array(first), native_stop=np.array(stop))
    if count < 4096:
        raise ValueError('A full physical observer window is required')
    source.update(clock, query=z['phase_grid_indices'], positions=z['source_coordinates'],
        source_taps=z['source_filter_taps'], native_start=np.array(start), count=np.array(count),
        interval_virtual_margin=np.array(margin), raw=raw, source_FIR=filtered)
    return clock, source


def sampled(z, source, clock, name, up):
    audio = z['audio'] if name == 'source' else z['wave']
    if name not in ('source', 'candidate'):
        raise ValueError('Explicit source or fitted candidate required')
    return render(clock, audio, z['phase_grid_indices'], float(source['native_start']),
        int(source['count']), up)
