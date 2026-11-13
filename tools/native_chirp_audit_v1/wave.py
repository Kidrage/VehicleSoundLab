"""Independent complex waves, exact arithmetic replay and original chirp contracts."""
import math
import numpy as np

def near(x, y, tol=1e-10):
    error = float(abs(np.asarray(x) - np.asarray(y)).max(initial=0))
    assert error <= tol, (error, tol)
    return error

def audit_wave(z, row, plan):
    if not row['lines']:
        assert not row['success'] and row['reason'] == 'empty_or_overflow'
        return dict(lines=0, waveform_error=0., support_error=0.)
    x, nominal, p = z['audio'], z['nominal'], z['parameters']
    n, m = len(x), len(nominal)
    assert len(row['lines']) == m and row['evaluations'] <= plan['max_evaluations']
    assert row['success'] == (row['status'] > 0)
    assert x.shape == (12000, 2) and len(p) == 4 * m + 1
    t = np.array([(i - n / 2) / 48000 for i in range(n)])
    co = np.column_stack((p[2 * m:], z['right_coefficients']))
    angle = 2 * np.pi * (t[:, None] * (nominal + p[:m]) + .5 * t[:, None] ** 2 * p[m:2 * m])
    independent = np.real(np.exp(1j * angle) @ (co[:m] - 1j * co[m:2 * m])) + co[-1]
    error = max(near(independent, z['reconstructed'], 2e-12), near(x - independent, z['residual'], 2e-12))
    # Replay original grouping after independent complex-wave verification. This
    # preserves defined support ratios for ill-conditioned exact-null controls.
    original_t = np.arange(n) / 48000 - n / 96000
    original_angle = 2 * np.pi * (original_t[:, None] * (nominal + p[:m]) + .5 * original_t[:, None] ** 2 * p[m:2 * m])
    cosine, sine = np.cos(original_angle), np.sin(original_angle)
    stems = cosine[:, :, None] * co[:m] + sine[:, :, None] * co[m:2 * m]
    grouped = stems.sum(axis=1) + co[-1]
    near(grouped, z['reconstructed'], 2e-12)
    near(x - stems.sum(axis=1) - co[-1], z['residual'], 2e-12)
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(n) / n)
    w = np.sqrt(window / n)
    design = np.column_stack((cosine, sine, np.ones(n)))
    singular = np.linalg.svd(w[:, None] * design, compute_uv=False)
    rank = int(sum(singular > singular[0] * max(design.shape) * np.finfo(float).eps))
    assert rank == row['rank']
    near(design.T @ (w ** 2 * (design @ co[:, 1] - x[:, 1])), np.zeros(2 * m + 1), 1e-11)
    left_error = cosine @ co[:m, 0] + sine @ co[m:2 * m, 0] + co[-1, 0] - x[:, 0]
    near(.5 * math.fsum((w * left_error) ** 2), row['cost'], 1e-12)
    residual = z['residual']
    near(np.linalg.norm(w[:, None] * residual, axis=0) / np.linalg.norm(w[:, None] * x, axis=0), row['weighted_relative_residual_LR'])
    width = np.full(m, 2.)
    if m > 1:
        gap = np.diff(nominal)
        width = np.minimum(width, .45 * np.minimum(np.r_[np.inf, gap], np.r_[gap, np.inf]))
    near(width, row['frequency_offset_bounds_hz'])
    near(z['lower'][:m], -width)
    near(z['upper'][:m], width)
    assert np.all(z['lower'][m:2 * m] == -500) and np.all(z['upper'][m:2 * m] == 500)
    near(z['initial'][:m], np.zeros(m))
    amp = np.hypot(co[:m], co[m:2 * m])
    powers = .5 * np.mean(amp * amp, axis=1)
    floor = max(powers) * 10 ** (-42 / 10)
    hz = np.fft.rfftfreq(n, 1 / 48000)
    zr = np.fft.rfft(residual * window[:, None], axis=0)
    support_error = 0.
    for k, line in enumerate(row['lines']):
        f, q = nominal[k] + p[k], p[m + k]
        near([f, q], [line['frequency_hz'], line['chirp_hz_per_second']])
        near(amp[k], line['amplitude_LR'])
        near(co[k], line['cosine_LR'])
        near(co[m + k], line['sine_LR'])
        near(np.arctan2(-co[m + k], co[k]), line['phase_at_midpoint_LR'])
        extent = abs(q) * n / 96000 + 8
        mask = (hz >= f - extent) & (hz <= f + extent)
        zl = np.fft.rfft(stems[:, k] * window[:, None], axis=0)
        before = np.sum(abs((zr + zl)[mask]) ** 2, axis=0)
        after = np.sum(abs(zr[mask]) ** 2, axis=0)
        supported = 1 - np.divide(after, before, out=np.ones(2), where=before > 0)
        support_error = max(support_error, near(supported, line['local_explained_fraction_LR'], 1e-9))
        contact = bool(abs(p[k]) >= width[k] - 1e-7 or abs(q) >= 500 - 1e-7)
        good = bool(row['success'] and rank == 2 * m + 1 and not contact and powers[k] >= floor and powers[k] > 0 and min(supported) >= .8)
        assert line['bound_contact'] == contact and line['relative_power_ok'] == (powers[k] >= floor) and line['eligible'] == good
    return dict(lines=m, waveform_error=error, support_error=support_error)
