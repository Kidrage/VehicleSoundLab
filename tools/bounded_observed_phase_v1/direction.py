"""Intersect positive phase-control and strictly monotonic-coordinate rays."""
import numpy as np


def phase_size(curve, interior):
    centered = curve-np.median(curve[interior])
    return float(np.percentile(abs(centered[interior]), 95))


def ray(time, basis, current, direction, bound):
    candidates = []
    for index, value in enumerate(direction):
        if value > 0: limit = (bound-current[index])/value
        elif value < 0: limit = (-bound-current[index])/value
        else: continue
        candidates.append(dict(kind='phase_control', index=index, limit=float(limit), inclusive=True))
    base = np.diff(time+basis@current); slope = np.diff(basis@direction)
    if base.min() <= 0 or np.max(abs(current)) > bound+1e-12:
        raise ValueError('Base phase must satisfy original bound and strict monotonicity')
    for index in np.flatnonzero(slope < 0):
        candidates.append(dict(kind='coordinate_increment', index=int(index), limit=float(-base[index]/slope[index]), inclusive=False))
    if not candidates: raise ValueError('Ray has no finite phase-control bound')
    active = min(candidates, key=lambda row: row['limit'])
    return dict(maximum_scale=active['limit'], limiting_constraint=active,
        constraints_checked=len(candidates))


def construct(time, basis, current, direction, bound, interior, target):
    vector = direction.copy()
    pivot = int(np.argmax(abs(vector)))
    if vector[pivot] < 0: vector *= -1
    curve = basis@vector; size = phase_size(curve, interior)
    if size <= 0 or not np.isfinite(size):
        raise ValueError('Direction has no finite nonzero interior-relative phase shape')
    factor = target/size; cases = []
    for sign in (-1, 1):
        evidence = ray(time, basis, current, sign*vector, bound)
        candidate = current+sign*factor*vector
        phase = basis@candidate
        violation = float(max(0., np.max(abs(candidate))-bound))
        increment = float(np.diff(time+phase).min())
        cases.append(dict(sign=sign, **evidence, original_phase_violation=violation,
            minimum_coordinate_increment=increment,
            target_feasible=bool(violation <= 1e-12 and increment > 0),
            maximum_ray_interior_phase_p95=evidence['maximum_scale']*size,
            target_scale=factor))
    return vector, curve, dict(canonical_sign_pivot=pivot, unit_interior_p95=size,
        unit_whole_maximum=float(abs(curve).max()), target_interior_p95=target,
        target_scale=factor, cases=cases, both_targets_feasible=all(row['target_feasible'] for row in cases))
