"""A measured multi-line lattice; never substitutes predictions for observations."""
import numpy as np
from scipy import signal
from state_colour_v2.clock import peaks


def track(observed, start, stop, anchor, plan):
    times = observed['seconds']
    selected = np.flatnonzero((times >= start-1e-8) & (times <= stop+1e-8))
    roots = np.geomspace(*plan['root_range_hz'], plan['grid_count'])
    orders = np.asarray(plan['orders'])
    score = np.empty((len(selected), len(roots)))
    counts = np.zeros_like(score, dtype=np.int16)
    spreads = np.zeros_like(score)
    minimum = plan['minimum_observed_lines']
    for row, index in enumerate(selected):
        frequencies, prominence = peaks(observed['hz'], observed['power_low'][:, index])
        if not len(frequencies):
            score[row] = -np.inf
            continue
        wanted = roots[:, None] * orders[None, :]
        distances = abs(wanted[:, :, None] - frequencies[None, None, :])
        nearest = distances.argmin(axis=2)
        error = np.take_along_axis(distances, nearest[:, :, None], axis=2)[:, :, 0]
        tolerance = np.maximum(6, .025*wanted)
        supported = (error <= tolerance) & (wanted < 1200) & (wanted >= 35)
        # Distinct orders must not count one observed peak twice.
        for j in range(len(orders)):
            if j:
                supported[:, j] &= ~np.any((nearest[:, j, None] == nearest[:, :j]) & supported[:, :j], axis=1)
        weights = np.clip(prominence[nearest]/16, .25, 1)
        score[row] = np.sum(supported * weights * np.exp(-.5*(error/tolerance)**2), axis=1)
        counts[row] = supported.sum(axis=1)
        measured_roots = frequencies[nearest] / orders[None, :]
        bound = np.where(supported, abs(measured_roots-roots[:, None]), 0)
        spreads[row] = bound.max(axis=1)
        score[row, counts[row] < minimum] = -np.inf
    if len(selected) < 3 or np.any(~np.isfinite(score).any(axis=1)):
        missing = times[selected[~np.isfinite(score).any(axis=1)]].tolist()
        return dict(status='missing_measured_consensus', rows=[], missing_seconds=missing)
    delta = np.log2(roots[1]/roots[0])
    seed_distance = abs(np.log2(roots/anchor))
    state = np.where(seed_distance <= .12, score[0]-(seed_distance/.12)**2, -np.inf)
    links = np.empty((len(selected)-1, len(roots)), dtype=np.int16)
    for row in range(1, len(selected)):
        dt = times[selected[row]]-times[selected[row-1]]
        radius = int(np.floor(plan['maximum_octaves_per_second']*dt/delta))
        offsets = np.arange(-radius, radius+1)
        previous = np.arange(len(roots))[None, :]+offsets[:, None]
        valid = (previous >= 0) & (previous < len(roots))
        clipped = np.clip(previous, 0, len(roots)-1)
        values = state[clipped]-.025*(offsets[:, None]*delta/dt)**2
        values[~valid] = -np.inf
        at = values.argmax(axis=0)
        links[row-1] = clipped[at, np.arange(len(roots))]
        state = values[at, np.arange(len(roots))]+score[row]
    if not np.isfinite(state).any():
        return dict(status='disconnected_measured_consensus', rows=[])
    path = [int(state.argmax())]
    for link in reversed(links):
        path.append(int(link[path[-1]]))
    path.reverse()
    measured = roots[path]
    rate = 1/float(np.median(np.diff(times[selected])))
    smoothed = signal.sosfiltfilt(signal.butter(4, plan['smoothing_hz'], fs=rate, output='sos'), measured)
    smooth_at = np.argmin(abs(smoothed[:, None]-roots[None, :]), axis=1)
    constrained = counts[np.arange(len(selected)), smooth_at] < minimum
    for row in np.flatnonzero(constrained):
        valid = np.flatnonzero(np.isfinite(score[row]))
        at = valid[np.argmin(abs(roots[valid]-smoothed[row]))]
        smoothed[row] = roots[at]
    velocity = abs(np.diff(np.log2(smoothed))/np.diff(times[selected]))
    if np.max(velocity)>plan['maximum_octaves_per_second']+1e-8:
        return dict(status='constrained_consensus_disconnected', rows=[])
    rows = [dict(seconds=float(times[index]), root_hz=float(smoothed[row]),
                 measured_lattice_root_hz=float(roots[at]),
                 smoothing_constrained_to_observation=bool(constrained[row]),
                 observed_lines=int(counts[row, at]), measured_root_spread_hz=float(spreads[row, at]),
                 lattice_score=float(score[row, at])) for row, (index, at) in enumerate(zip(selected, path))]
    return dict(status='measured_consensus', rows=rows,
                uncertainty='Per-frame measured-root spread, not a calibrated probability or physical RPM error',
                smoothing_hz=plan['smoothing_hz'],
                policy='At least three distinct measured peaks at every requested frame and smoothed position; zero-phase root smoothing, no missing-frame filling')
