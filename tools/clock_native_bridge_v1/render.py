"""Common physical grid, finite phase reconstruction and aligned native FIR."""
import numpy as np
from scipy import signal
from native_error_budget_v1.interpolate import reconstruct
from native_clock_render_v1.filter import taps
from .inverse import invert


def render(model, audio, sample_indices, native_start, count, up, *, old_positions=None):
    if (type(count) is not int or count < 1 or up not in (16, 32) or not np.isfinite(native_start)
            or np.shape(audio) != (len(sample_indices), 2) or np.any(np.diff(sample_indices) != 1)):
        raise ValueError('Finite source-grid audio, integer count and declared16/32 required')
    kernel = taps(up); delay = len(kernel)//2
    ticks = np.arange(-delay, (count-1)*up+delay+1)
    times = native_start+ticks/(48000*up)
    if old_positions is None:
        query = invert(model, times)
    else:
        if times[0] < old_positions[0] or times[-1] > old_positions[-1]:
            raise ValueError('Original PL inverse lacks genuine context')
        query = np.interp(times, old_positions, sample_indices)
    source_query = query-sample_indices[0]
    dense = reconstruct(audio, source_query, 128)
    filtered = signal.fftconvolve(dense, kernel[:, None], mode='valid', axes=0)
    output = filtered[::up]
    assert output.shape == (count, 2)
    return dict(query=query, dense_times=times, dense_wave=dense, native=output, taps=kernel)
