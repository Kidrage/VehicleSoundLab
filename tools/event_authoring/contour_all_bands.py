"""Optional four-band event time shapes using the existing runtime controls."""
from copy import deepcopy

import numpy as np

from .contour_joint import fit_shape as fit_fixed, shape_errors
from .contour_knots import fit_shape as fit_adaptive
from .contract import validate
from .measure import EDGES
from .response_basis import calibrate_unit
from .temporal_fit import band_curves


def observations(x, background):
    time, raw = band_curves(x)
    _, noise = band_curves(background)
    if len(time) < 16:
        raise ValueError('多段包络需要至少16帧分析数据，请使用更长的单次动作片段')
    floor = noise.mean(axis=1)
    contrasts = 10*np.log10(np.maximum(raw.mean(axis=1), 1e-30)/np.maximum(floor, 1e-30))
    target = np.maximum(raw-floor[:, None], 0)
    rows = [dict(hz=[lo, hi], contrast_db=float(contrasts[k]), selected=bool(contrasts[k] >= 3),
                 reason='At least3dB band event/background contrast' if contrasts[k] >= 3
                        else 'Band contrast below3dB; retain original local envelopes')
            for k, (lo, hi) in enumerate(EDGES)]
    return time, target, rows


def fit(profile, x, background, arrays):
    duration = len(x)/48000
    _, target, rows = observations(x, background)
    indices = [k for k, row in enumerate(rows) if row['selected']]
    report = dict(method='band-contour-v4', bands=rows, selected_attempt=None,
                  qualified=False, groups_include_low_mid=True)
    if not indices:
        report['reason'] = 'No band has3dB event/background contrast'
        return deepcopy(profile), report, None
    baseline = shape_errors(profile, target, duration, indices)
    weights = 1/np.maximum(baseline, .05)
    attempts, candidates = [], []
    # Two layouts and two bounded shape/spectrum alternations. No subset search
    # or change to component counts, the runtime interpolator or spectral gates.
    for layout in ('fixed', 'adaptive'):
        p = deepcopy(profile)
        for step in range(2):
            if layout == 'fixed':
                p, shape = fit_fixed(p, target, duration, rows, band_offset=0, weights=weights)
            else:
                p, shape = fit_adaptive(p, target, duration, rows, adaptive_indices=indices,
                                       weights=weights, band_offset=0)
            p, response = calibrate_unit(p, arrays, duration)
            errors = shape_errors(p, target, duration, indices)
            nonregression = all(a <= b+1e-10 for a, b in zip(errors, baseline))
            qualified = bool(response['qualified'] and nonregression)
            score = float(np.mean((np.asarray(errors)*weights)**2))
            index = len(attempts)
            attempts.append(dict(layout=layout, step=step, shape=shape, shape_rmse=errors,
                                 response=response, temporal_nonregression=nonregression,
                                 qualified=qualified, score=score))
            if qualified:
                candidates.append((score, index, deepcopy(p), response))
    report.update(baseline_shape_rmse=baseline, attempts=attempts,
        policy='All four existing60..14000Hz groups may qualify independently at3dB; weak groups retain local envelopes. Compare fixed/adaptive<=8 linear amplitude controls, two shape/spectral alternations each. Select minimum mean-normalized shape score weighted by inverse max(entry RMSE,.05); original six spectral gates and per-selected-band nonregression remain mandatory.',
        limitations='Hann band-power curves describe coarse acoustic energy, not isolated physical modes, fine texture or RPM. No source separation or automatic event extent/classification. Existing runtime capacity only; source timbre and held-out seeds require independent checking.')
    if not candidates:
        report['reason'] = 'No four-band layout passes original spectral and temporal nonregression gates'
        return deepcopy(profile), report, attempts[-1]['response']
    _, choice, p, response = min(candidates, key=lambda row: (row[0], row[1]))
    report.update(qualified=True, selected_attempt=choice,
                  adaptive_selected=attempts[choice]['layout'] == 'adaptive')
    return validate(p), report, response
