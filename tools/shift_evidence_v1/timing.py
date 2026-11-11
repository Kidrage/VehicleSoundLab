"""Persistent acoustic descent and interval-censored display-delay checks."""
import numpy as np
from drive_evidence_v1.family import peaks


def guided_peaks(observed, guide_times, guide_hz):
    """Short-window sensitivity, explicitly conditioned on the 80ms path.

    Only observed peaks are returned. Missing/remote peaks stay NaN; neither
    interpolation of the guide nor a clock prior fills measurement gaps.
    """
    times = observed['seconds']
    keep = np.flatnonzero((times >= guide_times[0]) & (times <= guide_times[-1]))
    frequencies = np.full(len(keep), np.nan)
    support = np.zeros((len(keep), 3))
    for j, i in enumerate(keep):
        hz, prominence = peaks(observed['hz'], observed['power_low'][:, i])
        prediction = float(np.interp(times[i], guide_times, guide_hz))
        if not len(hz):
            continue
        nearest = int(np.argmin(abs(hz - prediction)))
        if abs(hz[nearest] - prediction) > max(12., .04 * prediction):
            continue
        # Prominence alone admits tiny Hann sidelobes when the reference is
        # absent. This explicit conservative gate is relative to the observed
        # low-band peak, not an estimated sensor noise floor or probability.
        spectrum = observed['power_low'][:, i]
        if np.interp(hz[nearest], observed['hz'], spectrum) < spectrum.max() * 1e-3:
            continue
        frequencies[j] = hz[nearest]
        for k, multiple in enumerate((2, 3, 7)):
            target = hz[nearest] * multiple / 5
            at = int(np.argmin(abs(hz - target)))
            if abs(hz[at] - target) <= max(6., .025 * target):
                support[j, k] = np.clip(prominence[at], 0, 40) / 40
    return times[keep], frequencies, support


def descent(times, reference_hz, lo, hi):
    candidates = []
    for at in times[(times >= lo) & (times <= hi)]:
        before = reference_hz[(times >= at - .20) & (times < at - .10)]
        after = reference_hz[(times >= at + .10) & (times < at + .20)]
        before, after = before[np.isfinite(before)], after[np.isfinite(after)]
        if len(before) >= 10 and len(after) >= 10:
            pre, post = float(np.median(before)), float(np.median(after))
            candidates.append((post / pre, float(at), pre, post))
    ratio, at, pre, post = min(candidates)
    if ratio >= .9:
        raise ValueError('No sustained >10% descent in the declared search window')
    # Descriptive threshold crossing only. Frequency continues to accelerate;
    # this is neither clutch travel nor the duration of a torque-cut command.
    local = (times >= at - .15) & (times <= at + .15) & np.isfinite(reference_hz)
    lt, lf = times[local], reference_hz[local]
    crossings = []
    for fraction in (.25, .75):
        indices = np.flatnonzero(lf <= pre + fraction * (post - pre))
        crossings.append(float(lt[indices[0]]) if len(indices) else None)
    return dict(marker_seconds=at, before_hz=pre, after_hz=post, ratio=ratio,
                acoustic_25_75_crossing_seconds=crossings,
                acoustic_25_75_duration_seconds=(crossings[1] - crossings[0]
                    if None not in crossings else None))


def delay_intervals(events):
    # Brackets are observational bounds, not probability/confidence intervals.
    intervals = np.array([[e['display']['last_old_seconds'] - e['marker_seconds'],
                           e['display']['first_new_seconds'] - e['marker_seconds']]
                          for e in events])
    common = [float(intervals[:, 0].max()), float(intervals[:, 1].min())]
    omitted = []
    for i, event in enumerate(events):
        train = np.delete(intervals, i, axis=0)
        low, high = float(train[:, 0].max()), float(train[:, 1].min())
        held = intervals[i]
        prediction = (low + high) / 2 if low <= high else None
        omitted.append(dict(held_out_gear=event['display']['to'],
            training_intersection_seconds=[low, high],
            midpoint_prediction_seconds=prediction,
            held_out_interval_seconds=held.tolist(),
            midpoint_inside_held_out=bool(prediction is not None and held[0] <= prediction <= held[1]),
            any_training_delay_inside_held_out=bool(max(low, held[0]) <= min(high, held[1]))))
    return dict(sign='display boundary minus acoustic-descent marker; positive = display later',
                per_event_seconds=intervals.tolist(), common_intersection_seconds=common,
                common_delay_feasible=bool(common[0] <= common[1]), leave_one_out=omitted,
                interpretation='Combined A/V and display latency only; not separately identifiable, not actuator timing')
