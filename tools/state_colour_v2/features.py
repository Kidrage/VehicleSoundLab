"""Shared harmonic-power features; importing never runs an analysis."""
import numpy as np

REFERENCE_HZ = 46.875
BANDS = ((28, 120), (120, 400), (400, 1200), (1200, 3000), (3000, 6000))
HZ = REFERENCE_HZ * np.arange(1, 289)


def powers(power):
    return np.array([power[(HZ >= lo) & (HZ < hi)].sum(axis=0)
                     for lo, hi in BANDS])


def shape_delta(before, after):
    a, b = powers(before), powers(after)
    scalar = 10 * np.log10(b.sum(axis=0) / a.sum(axis=0))
    return 10 * np.log10(b / a) - scalar


def select_windows(evidence, rising):
    center = np.asarray(evidence['window_root_hz'])
    direction = np.gradient(center, np.asarray(evidence['window_source_seconds']))
    return ((center >= 45) & (center < 50) &
            (direction > 0 if rising else direction < 0))
