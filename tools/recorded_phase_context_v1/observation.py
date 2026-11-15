"""Complete-window carrier observations on an explicitly indexed coarse grid."""
import numpy as np
from exterior_clock_v1.warp import CYCLE, carrier_rows


class ContextRejected(ValueError):
    """A missing observation is never silently replaced by extrapolation."""


def observe(audio, first_index, reference=5):
    centers, rows = carrier_rows(audio, reference)
    centers += first_index
    # carrier_rows removes the LOCAL start phase; index the wider grid in the
    # same original coordinate. first_index is an integer number of cycles.
    rows *= np.exp(-2j*np.pi*reference*first_index/CYCLE)
    size = 4*CYCLE
    starts = (centers-first_index-size/2).astype(int)
    rms = np.array([np.sqrt(np.mean(audio[s:s+size, 0]**2)) for s in starts])
    strength = abs(rows[:, 0])/np.maximum(rms, 1e-300)
    if not np.isfinite(strength).all() or np.min(strength) < .02:
        raise ContextRejected('weak_or_missing_reference')
    return centers, rows, strength


def corrected_grid(coarse_audio, coarse_first, original_audio, reference=5):
    centers, rows, strength = observe(coarse_audio, coarse_first, reference)
    old_centers, old_rows = carrier_rows(original_audio, reference)
    old_slots = np.searchsorted(centers, old_centers)
    if not np.array_equal(centers[old_slots], old_centers):
        raise ContextRejected('original_window_grid_not_preserved')
    # Original complete windows are identical samples. Preserve their actual
    # evaluated complex numbers as well, avoiding coordinate-origin roundoff.
    if np.max(abs(rows[old_slots]-old_rows)) > 2e-12:
        raise ContextRejected('original_window_samples_changed')
    rows[old_slots] = old_rows
    angle = np.unwrap(np.angle(rows[:, 0]))
    if np.max(abs(np.diff(angle))) > .8*np.pi:
        raise ContextRejected('disconnected_reference_phase')
    correction = (angle-angle[old_slots[0]])/(2*np.pi*reference)
    original_angle = np.unwrap(np.angle(old_rows[:, 0]))
    correction[old_slots] = (original_angle-original_angle[0])/(2*np.pi*reference)
    indices = np.arange(int(centers[0]), int(centers[-1])+1)
    phase = indices/CYCLE+np.interp(indices, centers, correction)
    if np.min(np.diff(phase)) <= 0:
        raise ContextRejected('nonmonotonic_measured_phase')
    return dict(centers=centers, rows=rows, reference_strength=strength,
                correction=correction, indices=indices, phase=phase,
                original_slots=old_slots)
