"""Independent raw-adjoint quadrature and complete-moment covariance controls."""
import math
import numpy as np
from aperture_model_v1.forward import real_rows
from native_observation_v1.noise_geometry import sample_rows
from .adjoint import native_adjoint


def controls(native, operator, plan):
    frames = len(operator.basis)
    count = len(native.starts)*len(native.bins)
    tolerance = plan['rules']['maximum_forward_check_error']
    rng = np.random.default_rng(381062)
    real = rng.normal(size=(2*count, 3))
    fast = native_adjoint(native, real, frames)
    direct = np.zeros_like(fast)
    for index, start in enumerate(native.starts):
        matrix, _ = sample_rows(native, start)
        local = np.vstack((real[index*len(native.bins):(index+1)*len(native.bins)],
            real[count+index*len(native.bins):count+(index+1)*len(native.bins)]))
        direct[start:start+native.size] += matrix.T@local
    adjoint_error = float(abs(fast-direct).max())
    assert adjoint_error <= tolerance
    sample = rng.normal(size=frames)
    left = real_rows(native.apply(sample))@real[:, 0]
    right = sample@fast[:, 0]
    dot_error = float(abs(left-right)/max(1., abs(left), abs(right)))
    assert dot_error <= tolerance
    gram = operator.basis.T@operator.basis
    covariance_error = float(abs(gram-np.eye(len(gram))).max())
    assert covariance_error <= tolerance
    time = np.arange(frames)/plan['samples_per_cycle']
    waves = []
    for order in (3., 3.1, 8.37, 9.13, 10., 15.):
        waves.append((f'tone_{order}', .2*np.cos(2*np.pi*order*time+.31)))
    epsilon = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2)
    for label in ('rapid_common', 'occluded_partial', 'local_phase'):
        signal = np.zeros_like(time)
        for index, order in enumerate((2., 3., 5., 7.)):
            amplitude = .03*(1+.08*np.sin(2*np.pi*.023*time+.2*index))
            if label == 'occluded_partial' and index == 1:
                amplitude *= 1-.95*np.exp(-((time-20)/.8)**4)
            angle = 2*np.pi*order*(time+epsilon)+.17*index
            if label == 'local_phase' and index == 2:
                angle += .6*np.sin(2*np.pi*.17*time)
            signal += amplitude*np.cos(angle)
        waves.append((label, signal))
    rows = []
    scalar_error = 0.
    for label, signal in waves:
        measured = operator.real_apply(signal)
        packed = real_rows(operator.apply(signal))[:len(measured)]
        assert np.array_equal(packed, measured)
        for index in (0, len(measured)//2, len(measured)-1):
            direct = operator.scale*math.fsum(float(x*y) for x, y in zip(operator.basis[:, index], signal))
            scalar_error = max(scalar_error, abs(direct-measured[index]))
        energy = float(measured@measured)
        bound = float(operator.real_noise_variance*(signal@signal))
        assert energy <= bound+tolerance
        rows.append(dict(id=label, score_energy=energy, raw_source_norm_bound=bound,
                         captured_fraction=energy/bound))
    assert scalar_error <= tolerance
    matrix = np.column_stack((sample, waves[0][1], waves[-1][1]))
    combined = operator.real_apply(matrix)
    column_error = max(float(abs(combined[:, i]-operator.real_apply(matrix[:, i])).max()) for i in range(3))
    assert column_error <= tolerance
    return dict(passed=True, source_adjoint_maximum_error=adjoint_error, adjoint_relative_error=dot_error,
        global_white_covariance_maximum_error=covariance_error, scalar_moment_maximum_error=scalar_error,
        matrix_column_maximum_error=column_error, analytic_waveform_energies=rows,
        all_time_overlap_in_covariance=True, per_real_score_noise_variance=operator.real_noise_variance,
        known_forward_controls_only=True, phase_estimator_qualified=False)
