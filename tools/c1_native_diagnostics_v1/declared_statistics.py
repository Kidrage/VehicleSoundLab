"""Independent moments with the observed FP64 sequential centering declared.

The older fsum-centered comparison is still reported, including failures.
This separate oracle verifies the saved observer's actual arithmetic, not a
claim that distinct rounded centering conventions agree in vanishing moments.
"""
import math
import numpy as np
from clock_native_bridge_v1.audit_observation import verify as original_observe


def statistics(power, cross, ms):
    n = len(power)
    mean = np.zeros((6, 2))
    for frame in power:
        mean += frame
    mean /= n
    centered = power.reshape(n, 12)-mean.ravel()
    cov = np.array([[math.fsum(float(row[i])*float(row[j]) for row in centered)/n
        for j in range(12)] for i in range(12)])
    lagged = np.array([[[math.fsum(float(centered[k, i])*float(centered[k+lag, j])
        for k in range(n-lag))/(n-lag) for j in range(12)] for i in range(12)]
        for lag in range(1, min(9, n))])
    if not len(lagged):
        lagged = np.empty((0, 12, 12))
    cv = np.zeros((6, 2))
    defined = mean > 0
    cv[defined] = np.sqrt(np.diag(cov)).reshape(6, 2)[defined]/mean[defined]
    coherence = np.zeros(6, complex)
    denominator = np.sqrt(mean[:, 0])*np.sqrt(mean[:, 1])
    for band in range(6):
        if denominator[band] > 0:
            coherence[band] = complex(math.fsum(cross[:, band].real),
                math.fsum(cross[:, band].imag))/n/denominator[band]
    mid_side = np.zeros((6, 2))
    for frame in ms:
        mid_side += frame
    mid_side /= n
    return dict(mean_power=mean, power_defined=defined, CV=cv, covariance=cov,
        lag_covariance=lagged, complex_coherence=coherence,
        coherence_defined=denominator > 0, mean_mid_side=mid_side)


def verify(name, audio, saved, check, gates):
    old_failures = []

    def original_check(label, got, expected, scale, gate):
        got, expected = np.asarray(got), np.asarray(expected)
        assert got.shape == expected.shape and np.isfinite(got).all() and np.isfinite(expected).all()
        error = float(np.max(abs(got-expected))) if got.size else 0.
        relative = error/max(float(scale), 1e-300)
        if relative > gate and label.startswith(name+'_frozen_'):
            old_failures.append(dict(field=label, relative_error=relative,
                absolute_error=error, scale=float(scale), original_gate=gate, original_comparison_passed=False))
        else:
            check(label, got, expected, scale, gate)
    original = original_observe(name, audio, saved, original_check, gates)
    fields = statistics(saved[name+'_broad_power'], saved[name+'_broad_Gram'][:, :, 0, 1],
        saved[name+'_broad_mid_side'])
    for field, expected in fields.items():
        got = saved[name+'_broad_'+field]
        if expected.dtype == bool:
            assert np.array_equal(got, expected)
        else:
            scale = float(np.max(abs(expected))) if expected.size else 0.
            check(name+'_declared_center_'+field, got, expected, scale,
                gates['frozen_statistics_relative_nonzero_field_max'])
    return dict(original_operator=original, declared_centering_verified=True,
        original_fsum_centered_comparison_passed=not old_failures, retained_original_failures=old_failures,
        changed_producer_or_gate=False, certified_roundoff_or_acoustic_fidelity_claim=False)
