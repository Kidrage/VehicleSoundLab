"""Equivalent native chirp objective with exact linear nuisance elimination."""
import numpy as np
from scipy.linalg import qr, solve_triangular, lstsq
from scipy.optimize import least_squares

def projection(audio, nominal, weight, time):
    """Return residual/Jacobian functions and cached QR state, no true parameters."""
    nominal = np.asarray(nominal)
    m = len(nominal)
    cache = {}
    target = weight * audio
    def state(p):
        if 'p' in cache and np.array_equal(p, cache['p']):
            return cache
        angle = 2 * np.pi * (time[:, None] * (nominal + p[:m]) + .5 * time[:, None] ** 2 * p[m:])
        cosine, sine = np.cos(angle), np.sin(angle)
        design = np.column_stack((cosine, sine, np.ones(len(time))))
        weighted = weight[:, None] * design
        Q, R = qr(weighted, mode='economic', check_finite=False)
        coeff = solve_triangular(R, Q.T @ target, check_finite=False)
        residual = weighted @ coeff - target
        cache.clear()
        cache.update(p=p.copy(), cosine=cosine, sine=sine, design=design, weighted=weighted,
                     Q=Q, R=R, coefficients=coeff, residual=residual)
        return cache
    def fun(p):
        return state(p)['residual']
    def jac(p):
        s = state(p)
        co, cosine, sine, Q, R, residual = [s[k] for k in ['coefficients', 'cosine', 'sine', 'Q', 'R', 'residual']]
        factors = [2 * np.pi * time, np.pi * time ** 2]
        derivative = -sine * co[:m] + cosine * co[m:2 * m]
        V = np.column_stack([weight[:, None] * factor[:, None] * derivative for factor in factors])
        D = np.zeros((2 * m + 1, 2 * m))
        indices = np.arange(m)
        for block, factor in enumerate(factors):
            wr = weight * factor * residual
            D[indices, block * m + indices] = -(sine * wr[:, None]).sum(axis=0)
            D[m + indices, block * m + indices] = (cosine * wr[:, None]).sum(axis=0)
        return V - Q @ (Q.T @ V) - Q @ solve_triangular(R.T, D, lower=True, check_finite=False)
    return fun, jac, state

def fit(audio, nominal, chirp, plan):
    nominal = np.asarray(nominal, dtype=float)
    chirp = np.asarray(chirp, dtype=float)
    m, n = len(nominal), len(audio)
    if audio.shape != (plan['frames'], 2) or chirp.shape != nominal.shape or not np.isfinite(audio).all():
        raise ValueError('Finite native stereo and observed chirps required')
    if not m or m > plan['maximum_modes']:
        return dict(success=False, reason='empty_or_overflow', lines=[]), {}
    t = np.arange(n) / plan['sample_rate'] - n / (2 * plan['sample_rate'])
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(n) / n)
    w = np.sqrt(window / n)
    width = np.full(m, plan['frequency_radius_hz'])
    if m > 1:
        gaps = np.diff(nominal)
        if min(gaps) <= 0:
            raise ValueError('Ascending distinct native frequencies required')
        width = np.minimum(width, .45 * np.minimum(np.r_[np.inf, gaps], np.r_[gaps, np.inf]))
    limit = plan['maximum_chirp_hz_per_second']
    initial_reduced = np.r_[np.zeros(m), np.clip(chirp, -limit + 1e-6, limit - 1e-6)]
    lower_reduced, upper_reduced = np.r_[-width, np.full(m, -limit)], np.r_[width, np.full(m, limit)]
    fun, jac, state = projection(audio[:, 0], nominal, w, t)
    initial_coefficients = state(initial_reduced)['coefficients'].copy()
    initial = np.r_[initial_reduced, initial_coefficients]
    tol = plan['tolerance']
    solved = least_squares(fun, initial_reduced, jac=jac, bounds=(lower_reduced, upper_reduced),
        max_nfev=plan['max_evaluations'], ftol=tol, xtol=tol, gtol=tol, x_scale='jac')
    s = state(solved.x)
    right, _, rank, _ = lstsq(s['weighted'], w * audio[:, 1], lapack_driver='gelsy')
    p = np.r_[solved.x, s['coefficients']]
    coefficients = np.column_stack((s['coefficients'], right))
    stems = s['cosine'][:, :, None] * coefficients[:m] + s['sine'][:, :, None] * coefficients[m:2 * m]
    residual = audio - stems.sum(axis=1) - coefficients[-1]
    frequency, q = nominal + solved.x[:m], solved.x[m:]
    amplitude = np.hypot(coefficients[:m], coefficients[m:2 * m])
    power = .5 * np.mean(amplitude ** 2, axis=1)
    floor = power.max() * 10 ** (plan['minimum_line_power_db_relative_to_maximum'] / 10)
    contact = (abs(solved.x[:m]) >= width - 1e-7) | (abs(q) >= limit - 1e-7)
    zr = np.fft.rfft(residual * window[:, None], axis=0)
    hz = np.fft.rfftfreq(n, 1 / plan['sample_rate'])
    lines = []
    for k in range(m):
        extent = abs(q[k]) * n / (2 * plan['sample_rate']) + plan['support_padding_hz']
        selected = (hz >= frequency[k] - extent) & (hz <= frequency[k] + extent)
        zl = np.fft.rfft(stems[:, k] * window[:, None], axis=0)
        before = np.sum(abs((zr + zl)[selected]) ** 2, axis=0)
        after = np.sum(abs(zr[selected]) ** 2, axis=0)
        supported = 1 - np.divide(after, before, out=np.ones(2), where=before > 0)
        eligible = bool(solved.success and rank == 2 * m + 1 and not contact[k] and power[k] >= floor and power[k] > 0 and
                        min(supported) >= plan['minimum_local_explained_fraction'])
        lines.append(dict(index=k, nominal_hz=float(nominal[k]), frequency_hz=float(frequency[k]), chirp_hz_per_second=float(q[k]),
            amplitude_LR=amplitude[k].tolist(), phase_at_midpoint_LR=np.arctan2(-coefficients[m + k], coefficients[k]).tolist(),
            cosine_LR=coefficients[k].tolist(), sine_LR=coefficients[m + k].tolist(), bound_contact=bool(contact[k]),
            relative_power_ok=bool(power[k] >= floor), local_explained_fraction_LR=supported.tolist(), eligible=eligible))
    result = dict(success=bool(solved.success), reason=None, status=int(solved.status), message=solved.message,
        evaluations=int(solved.nfev), rank=int(rank), cost=float(solved.cost), optimality=float(solved.optimality),
        weighted_relative_residual_LR=(np.linalg.norm(w[:, None] * residual, axis=0) / np.maximum(np.linalg.norm(w[:, None] * audio, axis=0), 1e-300)).tolist(),
        frequency_offset_bounds_hz=width.tolist(), DC_LR=coefficients[-1].tolist(), lines=lines,
        nonlinear_parameter_count=2 * m, eliminated_linear_parameter_count=2 * m + 1,
        reduced_objective='Exact left native weighted LS, linear cos/sin/DC profiled by QR each frequency/rate step')
    arrays = dict(nominal=nominal, parameters=p, initial=initial, right_coefficients=right,
        lower=np.r_[lower_reduced, np.full(2 * m + 1, -np.inf)], upper=np.r_[upper_reduced, np.full(2 * m + 1, np.inf)],
        reconstructed=stems.sum(axis=1) + coefficients[-1], residual=residual,
        reduced_initial=initial_reduced, reduced_parameters=solved.x)
    return result, arrays
