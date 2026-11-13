"""Observation-only stage scale; frozen within each original trust-region step."""
import numpy as np


def choose(residual, floor):
    if residual.ndim != 1 or len(residual) == 0 or len(residual)%2:
        raise ValueError('Expected nonempty stacked real/imaginary residual')
    if not np.isfinite(residual).all() or not np.isfinite(floor) or floor <= 0:
        raise ValueError('Finite residual and positive floor required')
    count = len(residual)//2
    median = float(np.median(np.hypot(residual[:count], residual[count:])))
    return max(float(floor), median), median
