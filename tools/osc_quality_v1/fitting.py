"""Controlled changes to matching/window/budget; no high-layer additions."""
import numpy as np
from scipy.optimize import linear_sum_assignment
from sinusoidal_experiment import peaks, add_interval
from reference_osc_v1.exporter import channel_coefficients, write_model


def frames(audio, rate, window=4096, hop=256, maximum=128):
    return [(center, peaks(audio[center-window//2:center+window//2], rate, maximum))
        for center in range(window//2, len(audio)-window//2, hop)]


def assignments(previous, current, gated):
    if not len(previous) or not len(current):
        return []
    cost = abs(previous[:, None, 0]-current[None, :, 0])/np.maximum(16, previous[:, None, 0]*.045)
    if gated:
        m, n = cost.shape
        matrix = np.full((m+n, m+n), 1e6)
        matrix[:m, :n] = np.where(cost <= 1, cost, 1e6)
        matrix[np.arange(m), n+np.arange(m)] = .500001
        matrix[m+np.arange(n), np.arange(n)] = .500001
        matrix[m:, n:] = 0
        rows, cols = linear_sum_assignment(matrix)
        return [(i, j) for i, j in zip(rows, cols) if i < m and j < n and cost[i, j] <= 1]
    rows, cols = linear_sum_assignment(cost)
    return [(i, j) for i, j in zip(rows, cols) if cost[i, j] <= 1]


def weighted_percentile(values, weights, quantiles=(.5, .9, .99)):
    values, weights = np.asarray(values), np.asarray(weights)
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    if not len(cumulative) or cumulative[-1] <= 0:
        return []
    return np.interp(np.asarray(quantiles)*cumulative[-1], cumulative, values[order]).tolist()


def synthesize(audio, rate, observations, count=64, gated=False, hop=256):
    out = np.zeros_like(audio)
    previous = None
    stats = dict(matched=0, births=0, deaths=0, observed=0, analysed_frames=len(observations),
        matching='unmatched options before assignment' if gated else 'full assignment, then reject >1',
        peak_limit=count, hop=hop)
    errors, weights, relative, frequencies = [], [], [], []
    duration = hop/rate
    for center, detected in observations:
        current = detected[:count]
        stats['observed'] += len(current)
        if previous is not None:
            pairs = assignments(previous, current, gated)
            used_a, used_b = set(), set()
            for i, j in pairs:
                a, b = previous[i], current[j]
                add_interval(out, old_center, hop, rate, a, b)
                used_a.add(i)
                used_b.add(j)
                stats['matched'] += 1
                predicted = a[2]+np.pi*(a[0]+b[0])*duration
                endpoint = b[2]+2*np.pi*round((predicted-b[2])/(2*np.pi))
                epsilon = endpoint-predicted
                # Additional midpoint frequency caused by reconciling phase
                # and endpoint spectral frequencies. Not proved estimation error.
                bump = abs(1.5*epsilon/(2*np.pi*duration))
                weight = (a[1]**2+a[1]*b[1]+b[1]**2)*duration/6
                errors.append(bump)
                weights.append(weight)
                relative.append(bump/max((a[0]+b[0])/2, 1))
                frequencies.append((a[0]+b[0])/2)
            for i, a in enumerate(previous):
                if i not in used_a:
                    add_interval(out, old_center, hop, rate, a, [a[0], 0, a[2]+2*np.pi*a[0]*duration])
                    stats['deaths'] += 1
            for j, b in enumerate(current):
                if j not in used_b:
                    add_interval(out, old_center, hop, rate, [b[0], 0, b[2]-2*np.pi*b[0]*duration], b)
                    stats['births'] += 1
        previous, old_center = current, center
    stats['phase_reconciliation_midpoint_hz_weighted_p50_p90_p99'] = weighted_percentile(errors, weights)
    stats['phase_reconciliation_relative_weighted_p50_p90_p99'] = weighted_percentile(relative, weights)
    errors, weights, frequencies = np.asarray(errors), np.asarray(weights), np.asarray(frequencies)
    stats['phase_by_band'] = {}
    for lo, hi in [(80, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 14000)]:
        mask = (frequencies >= lo)&(frequencies < hi)
        stats['phase_by_band'][f'{lo}-{hi}'] = weighted_percentile(errors[mask], weights[mask])
    stats['mean_support'] = stats['observed']/max(len(observations), 1)
    return out, stats


def export_model(path, rate, length, observations, count=64, gated=True, hop=256):
    """Same measured pairs, precomputed coefficients for the unchanged C core."""
    segments = {}
    previous = None
    def interval(start, a, b):
        channel = channel_coefficients(a, b, hop, rate)
        segments.setdefault(start, []).append([0, *channel, *channel])
    for center, detected in observations:
        current = detected[:count]
        if previous is not None:
            pairs = assignments(previous, current, gated)
            used_a, used_b = set(), set()
            for i, j in pairs:
                interval(old_center, previous[i], current[j])
                used_a.add(i)
                used_b.add(j)
            for i, a in enumerate(previous):
                if i not in used_a:
                    interval(old_center, a, [a[0], 0, a[2]+2*np.pi*a[0]*hop/rate])
            for j, b in enumerate(current):
                if j not in used_b:
                    interval(old_center, [b[0], 0, b[2]-2*np.pi*b[0]*hop/rate], b)
        previous, old_center = current, center
    return write_model(path, rate, length, segments)
