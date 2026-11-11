"""Pitch-normalized harmonic observations with independent clock diagnostics."""
import numpy as np
from exterior_clock_v1.warp import warp, polish, carrier_rows, CYCLE
from sound_dna.windowed import coefficients


def describe(audio, source_start, times, roots, start, stop, reference=5, phase_refiner=polish):
    original, positions, initial = warp(audio, source_start, times, roots, start, stop)
    normalized, where, correction = phase_refiner(audio, source_start, original, positions,
                                                 reference, initial['source_cutoff_hz'])
    rows = coefficients(normalized, 288).reshape(-1, 288, 4)
    complex_rows = rows[:, :, ::2] + 1j*rows[:, :, 1::2]
    power = np.mean(abs(complex_rows)**2, axis=0)
    center_frames = np.arange(len(rows))*256 + 2*CYCLE
    center_seconds = np.interp(center_frames, np.arange(len(where)), where)
    local_roots = 1/(CYCLE*np.gradient(where))
    window_roots = np.interp(center_frames, np.arange(len(where)), local_roots)
    bounds = [[float(local_roots[start:start+4*CYCLE].min()),
               float(local_roots[start:start+4*CYCLE].max())]
              for start in np.arange(len(rows))*256]
    diagnostics = {}
    for order in (3, 5, 7, 10, 15, 20):
        _, values = carrier_rows(normalized, order)
        diagnostics[str(order)] = dict(fitted=order == reference,
            coherence=(abs(values.mean(axis=0))/np.maximum(np.mean(abs(values), axis=0), 1e-30)).tolist())
    return normalized, where, dict(initial=initial, correction=correction,
        windows=len(rows), normalized_cycles=len(normalized)/CYCLE,
        nonoverlapping_four_cycle_window_upper_bound=len(normalized)//(4*CYCLE),
        supported_hz_at_reference_root=(correction['source_cutoff_hz']-600)/max(local_roots)*46.875,
        harmonic_mean_power_LR=power.tolist(), diagnostics=diagnostics,
        window_source_seconds=center_seconds.tolist(), window_root_hz=window_roots.tolist(),
        window_root_hz_bounds=bounds), complex_rows


def match(rows, root_hz, bins):
    """Mean observed harmonic powers inside explicit root bins, per channel.

    No per-window level matching. Overlapping Hann windows are correlated,
    so counts below are coverage diagnostics, not independent sample counts.
    """
    result = []
    for low, high in bins:
        selected = (root_hz >= low) & (root_hz < high)
        result.append(dict(root_bin_hz=[low, high], windows=int(selected.sum()),
            mean_root_hz=float(root_hz[selected].mean()) if selected.any() else None,
            mean_power_LR=np.mean(abs(rows[selected])**2, axis=0).tolist() if selected.any() else None))
    return result


def difference(before, after, reference_hz=46.875):
    a, b = np.asarray(before), np.asarray(after)
    hz = reference_hz*np.arange(1, len(a)+1)
    bands = [(28, 120), (120, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 14000)]
    power_a = np.array([a[(hz >= lo) & (hz < hi)].sum(axis=0) for lo, hi in bands])
    power_b = np.array([b[(hz >= lo) & (hz < hi)].sum(axis=0) for lo, hi in bands])
    delta = 10*np.log10((power_b+1e-30)/(power_a+1e-30))
    full = 10*np.log10((b.sum(axis=0)+1e-30)/(a.sum(axis=0)+1e-30))
    return dict(bands_hz=bands, after_minus_before_db_LR=delta.tolist(),
        total_delta_db_LR=full.tolist(), shape_after_scalar_removal_db_LR=(delta-full).tolist(),
        reference_root_hz=reference_hz,
        scope='Equal acoustic-coordinate harmonic powers, not separated physical layers or load.')
