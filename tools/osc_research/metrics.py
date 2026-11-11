"""Recording-domain metrics; none are perceptual realism or noise percentages."""
import numpy as np
from scipy import signal

BANDS = [(80, 400), (400, 1200), (1200, 3000), (3000, 8000), (8000, 14000)]


def power_db(a, b):
    return float(10*np.log10(max(float(a), 1e-30) / max(float(b), 1e-30)))


def measure(audio, sr, reference=None, trim_seconds=.2):
    x = audio[round(sr*trim_seconds):-round(sr*trim_seconds)]
    f, p = signal.welch(x, sr, nperseg=4096, axis=0, detrend=False)
    _, cross = signal.csd(x[:, 0], x[:, 1], sr, nperseg=4096, detrend=False)
    mid = (x[:, 0] + x[:, 1]) * .5
    side = (x[:, 0] - x[:, 1]) * .5
    _, ms = signal.welch(np.column_stack((mid, side)), sr, nperseg=4096, axis=0, detrend=False)
    total = p.sum()
    out = dict(rms_dbfs=power_db(np.mean(x*x), 1),
               side_to_mid_db=power_db(np.mean(side*side), np.mean(mid*mid)),
               bands=[])
    for lo, hi in BANDS:
        mask = (f >= lo) & (f < hi)
        p_lr = p[mask].sum(axis=0)
        c = cross[mask].sum() / max(float(np.sqrt(p_lr.prod())), 1e-30)
        weights = np.sqrt(p[mask, 0]*p[mask, 1])
        msc = abs(cross[mask])**2 / np.maximum(p[mask, 0]*p[mask, 1], 1e-30)
        out['bands'].append(dict(hz=[lo, hi], power_fraction=float(p_lr.sum()/max(total, 1e-30)),
            lr_balance_db=power_db(p_lr[0], p_lr[1]),
            side_to_mid_db=power_db(ms[mask, 1].sum(), ms[mask, 0].sum()),
            integrated_complex_correlation=[float(c.real), float(c.imag)],
            weighted_magnitude_squared_coherence=float(np.sum(msc*weights)/max(weights.sum(), 1e-30))))
    if reference is not None:
        target = reference[round(sr*trim_seconds):-round(sr*trim_seconds)]
        out['relative_waveform_residual_db'] = power_db(np.mean((target-x)**2), np.mean(target*target))
        out['output_to_reference_power_db'] = power_db(np.mean(x*x), np.mean(target*target))
    return out


def compare(target, value):
    rows = []
    for a, b in zip(target['bands'], value['bands']):
        rows.append(dict(hz=a['hz'], side_to_mid_error_db=b['side_to_mid_db']-a['side_to_mid_db'],
            relative_band_fraction_error_db=power_db(b['power_fraction'], a['power_fraction']),
            complex_correlation_error=float(np.linalg.norm(np.array(b['integrated_complex_correlation'])-
                                                          a['integrated_complex_correlation'])),
            weighted_coherence_error=b['weighted_magnitude_squared_coherence']-a['weighted_magnitude_squared_coherence']))
    return rows
