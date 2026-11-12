"""Fit a single stereo coordinate from supported L partials; retain heldout lines."""
import numpy as np
from exterior_clock_v1.warp import CYCLE, render_positions
from phase_clock_v1.projection import independent_agreement
from startup_catch_v1.clock import diagnostics


def refine_once(audio, source_start, normalized, positions, cutoff, plan):
    size = plan['projection_cycles']*CYCLE
    starts = np.arange(0, len(normalized)-size+1, plan['hop_samples'])
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    fit = np.asarray(plan['fit_orders'])
    bins = plan['projection_cycles']*np.arange(1, 21)
    values = np.array([np.fft.rfft(normalized[start:start+size]*window[:, None], axis=0)[bins]
                       *2/window.sum() for start in starts])
    power = abs(values[:, :, 0])**2
    supported = power[:, fit-1] >= np.maximum(power.max(axis=1, keepdims=True), 1e-30)*10**(plan['support_relative_db']/10)
    if len(starts) < 3 or np.any(supported.sum(axis=1) < plan['minimum_fit_lines']):
        raise ValueError('Missing simultaneous phase observations; no phase filling')
    # Remove the known phase of each projection window's start.
    z = values[:, fit-1, 0]*np.exp(-2j*np.pi*starts[:, None]*fit[None, :]/CYCLE)
    alpha = np.full(len(fit), np.nan)
    correction = np.empty(len(starts))
    current = 0.
    # Initial unwrap supplies a branch only. The first window's arbitrary
    # partial offsets are recalibrated over all supported observations below.
    for row in range(len(starts)):
        active = supported[row]
        new = active & ~np.isfinite(alpha)
        alpha[new] = np.angle(z[row, new])-2*np.pi*fit[new]*current
        difference = np.angle(z[row, active]*np.exp(-1j*(alpha[active]+2*np.pi*fit[active]*current))) / (2*np.pi*fit[active])
        current += float(np.median(difference))
        correction[row] = current
    preferred = np.arange(len(fit))
    for iteration in range(plan['global_iterations']):
        for column, order in enumerate(fit):
            active = supported[:, column]
            alpha[column] = np.angle(np.mean(z[active, column]*np.exp(-2j*np.pi*order*correction[active])))
        error = np.angle(z*np.exp(-1j*(alpha[None, :]+2*np.pi*fit[None, :]*correction[:, None]))) / (2*np.pi*fit[None, :])
        residual = np.where(supported, abs(error), np.nan)
        reliability = np.nanpercentile(residual, 95, axis=0)
        preferred = np.argsort(reliability)[:plan['minimum_fit_lines']]
        for row in range(len(starts)):
            active = np.array([i for i in preferred if supported[row, i]])
            if len(active) < plan['minimum_fit_lines']:
                active = np.flatnonzero(supported[row])
            # Phase errors in radians have lower cycle uncertainty at larger
            # orders. A fixed globally consistent pair avoids median switching
            # between partials with different first-window offset errors.
            correction[row] += float(np.average(error[row, active], weights=fit[active]**2))
    final_error = np.angle(z*np.exp(-1j*(alpha[None, :]+2*np.pi*fit[None, :]*correction[:, None]))) / (2*np.pi*fit[None, :])
    retained_counts = np.sum(supported & (abs(final_error)<=plan['outlier_cycles']), axis=1)
    if np.any(retained_counts < plan['minimum_fit_lines']):
        raise ValueError('Incompatible calibrated phase lines; no forced common clock')
    centers = starts+size/2
    indices = np.arange(int(centers[0]), int(centers[-1])+1)
    phase = indices/CYCLE+np.interp(indices, centers, correction)
    if np.min(np.diff(phase)) <= 0:
        raise ValueError('Common measured phase is not monotonic')
    uniform = np.arange(int(np.ceil(phase[0]*CYCLE)), int(np.floor(phase[-1]*CYCLE)))/CYCLE
    at = np.interp(uniform, phase, indices)
    where = np.interp(at, np.arange(len(positions)), positions)
    roots = 1/(CYCLE*np.diff(where))
    final_cutoff = min(cutoff, .38*CYCLE*float(roots.min()))
    result = render_positions(audio, source_start, where, final_cutoff)
    checks = diagnostics(result, 0)
    for order, item in checks.items():
        item['fitted'] = int(order) in fit
    independent = independent_agreement({key: item for key, item in checks.items() if not item['fitted']})
    evidence = dict(fit_orders=fit.tolist(), preferred_orders=fit[preferred].tolist(),
        residual_p95_cycles=reliability.tolist(), global_iterations=plan['global_iterations'],
        correction_variation_p95_cycles=float(np.percentile(abs(correction-np.median(correction)), 95)),
        minimum_retained_lines=int(min(retained_counts)), fitted_lines=retained_counts.tolist(),
        diagnostics=checks, independent_agreement=independent,
        source_cutoff_hz=final_cutoff, source_seconds=[float(where[0]), float(where[-1])],
        root_hz_range=[float(roots.min()), float(roots.max())],
        processing='One common L-derived coordinate for unchanged original L/R; no independent channel alignment',
        edge_policy='Discard unsupported projection margins, no phase extrapolation')
    return result, where, evidence


def refine(audio, source_start, normalized, positions, cutoff, plan):
    """Fixed iterative alignment to reduce the projection window's phase lag.

    Every pass samples the ORIGINAL stereo, never the previous resampled PCM.
    Missing measurements still reject; no extra passes are tried on failure.
    """
    history = []
    for _ in range(plan['refinement_passes']):
        normalized, positions, evidence = refine_once(audio, source_start, normalized,
                                                      positions, cutoff, plan)
        cutoff = evidence['source_cutoff_hz']
        history.append(evidence)
    result = dict(history[-1], refinement_passes=plan['refinement_passes'], passes=history)
    return normalized, positions, result
