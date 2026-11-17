"""Reuse native finite spectral bookkeeping without discarding signed cross terms."""
import numpy as np
from native_projection_v1.budget import measure

EDGES = [[0,60], [60,300], [300,1200], [1200,4500], [4500,14000], [14000,24001]]
SPEC = dict(window_samples=2048, hop_samples=240, fft_samples=2048, rate=48000, bands_hz=EDGES)


def budgets(source, harmonic, remainder):
    arrays = measure(source, harmonic, remainder, SPEC)
    result = {'window_starts': arrays['window_starts']}
    for label, key in [('source', 'P_full'), ('projection', 'P_harmonic'),
                       ('remainder', 'P_remainder'), ('cross', 'cross_HR_RH')]:
        result[label] = np.trace(arrays[key], axis1=-2, axis2=-1).real/source.shape[1]
    difference = result['source']-result['projection']-result['remainder']-result['cross']
    rows = []
    for band, edge in enumerate(EDGES):
        values = {name: float(result[name][:, band].mean()) for name in ('source', 'projection', 'remainder', 'cross')}
        denom = max(values['source'], 1e-300)
        values.update(band_hz=edge, projection_to_raw=values['projection']/denom,
            remainder_to_raw=values['remainder']/denom, signed_cross_to_raw=values['cross']/denom,
            maximum_balance_error_FS2=float(abs(difference[:, band]).max()))
        rows.append(values)
    return rows, result
