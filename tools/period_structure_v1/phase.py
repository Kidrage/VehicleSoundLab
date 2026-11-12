"""Compare carrier timing without fitting or accepting a new common phase."""
from itertools import combinations
import numpy as np


def observe(audio, cycle, plan):
    orders = np.asarray(plan['orders'])
    size = cycle*plan['projection_cycles']
    starts = np.arange(0, len(audio)-size+1, plan['hop_samples'])
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    all_orders = np.arange(1, 21)
    values = np.array([np.fft.rfft(audio[start:start+size]*window[:, None], axis=0)
        [all_orders*plan['projection_cycles']] * 2/window.sum() for start in starts])
    supported = abs(values[:, orders-1])**2 >= np.maximum(abs(values).max(axis=1, keepdims=True)**2, 1e-30) * 10**(plan['support_relative_db']/10)
    z = values[:, orders-1]*np.exp(-2j*np.pi*starts[:, None, None]*orders[None, :, None]/cycle)
    result = []
    for first, second in combinations(range(len(orders)), 2):
        for channel in range(2):
            active = supported[:, first, channel] & supported[:, second, channel]
            edges = np.diff(np.r_[False, active, False].astype(int))
            segments = []
            for begin, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
                if stop-begin < plan['minimum_contiguous_rows']:
                    continue
                a = np.unwrap(np.angle(z[begin:stop, first, channel]))
                b = np.unwrap(np.angle(z[begin:stop, second, channel]))
                delta = a/(2*np.pi*orders[first])-b/(2*np.pi*orders[second])
                delta -= np.median(delta)
                maximum_step = float(max(np.max(abs(np.diff(a))), np.max(abs(np.diff(b)))))
                segments.append(dict(rows=int(stop-begin), from_cycle=float((starts[begin]+size/2)/cycle),
                    to_cycle=float((starts[stop-1]+size/2)/cycle),
                    p95_relative_drift_cycles=float(np.percentile(abs(delta), 95)),
                    max_relative_drift_cycles=float(max(abs(delta))), maximum_phase_step_radians=maximum_step,
                    unwrap_warning=maximum_step>plan['warning_phase_step_radians']))
            result.append(dict(orders=[int(orders[first]), int(orders[second])], channel='LR'[channel],
                simultaneous_support_fraction=float(active.mean()), segments=segments,
                worst_p95_relative_drift_cycles=max((part['p95_relative_drift_cycles'] for part in segments), default=None)))
    return dict(rows=len(starts), pairs=result,
        interpretation='Constant phase offsets removed separately within contiguous supported segments; no missing-row interpolation, retiming or common-clock acceptance')
