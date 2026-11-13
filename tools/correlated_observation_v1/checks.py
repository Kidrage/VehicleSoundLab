"""Independent real-QR geometry, scalar projections and source-energy controls."""
import numpy as np
from scipy.linalg import qr
from aperture_model_v1.forward import real_rows
from native_observation_v1.noise_geometry import sample_rows


def controls(operator, plan, rules):
    time = np.arange(operator.frames)/plan['samples_per_cycle']
    maximum = rules['maximum_forward_check_error']
    indices = (0, len(operator.starts)//2, len(operator.starts)-1)
    matrices, subspaces, covariance = {}, {}, []
    variance = operator.real_noise_variance
    for index in indices:
        start = operator.starts[index]
        original, _ = sample_rows(operator.base, start)
        transformed = operator.sample_matrix(start)
        q, r = qr(original.T, mode='economic')
        assert np.min(abs(r.diagonal())) > 0
        error = float(abs(transformed@transformed.T/variance-np.eye(len(transformed))).max())
        assert error <= maximum
        matrices[index], subspaces[index] = transformed, q
        covariance.append(dict(window_index=int(index), maximum_normalized_white_covariance_error=error,
                               original_real_rows=len(original), source_samples=operator.size))
    waves = []
    for order in (3., 3.1, 8.37, 9.13, 10., 15.):
        waves.append((f'tone_{order}', .2*np.cos(2*np.pi*order*time+.31)))
    epsilon = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2)
    for label in ('rapid_common', 'occluded_partial', 'local_phase'):
        signal = np.zeros_like(time)
        for k, order in enumerate((2., 3., 5., 7.)):
            amplitude = .03*(1+.08*np.sin(2*np.pi*.023*time+.2*k))
            if label == 'occluded_partial' and k == 1:
                amplitude *= 1-.95*np.exp(-((time-20)/.8)**4)
            angle = 2*np.pi*order*(time+epsilon)+.17*k
            if label == 'local_phase' and k == 2:
                angle += .6*np.sin(2*np.pi*.17*time)
            signal += amplitude*np.cos(angle)
        waves.append((label, signal))
    energies = []
    scalar_error = 0.
    for label, signal in waves:
        old = operator.base.apply(signal).reshape(len(operator.starts), -1)
        new = operator.apply(signal).reshape(len(operator.starts), -1)
        independent = []
        for index in indices:
            start = operator.starts[index]
            local = signal[start:start+operator.size]
            direct = np.array([2*np.sum(local*np.sin(np.pi*np.arange(operator.size)/operator.size)**2*
                np.exp(-2j*np.pi*order*time[start:start+operator.size]))/operator.window.sum()
                for order in operator.orders])
            rotation = np.exp(-2j*np.pi*operator.bins*start/operator.size)
            expected_complex = rotation*(operator.symmetric@(direct/rotation))
            scalar_error = max(scalar_error, float(abs(new[index]-expected_complex).max()))
            actual = float(np.sum(abs(new[index])**2))
            expected = float(variance*np.sum((subspaces[index].T@local)**2))
            bound = float(variance*np.sum(local**2))
            assert abs(actual-expected) <= maximum*max(1., bound)
            assert actual <= bound+maximum*max(1., bound)
            independent.append(dict(window_index=int(index), measured_energy=actual,
                independent_QR_energy=expected, source_norm_bound=bound))
        energies.append(dict(id=label, native_mean_window_energy=float(np.sum(abs(old)**2, axis=1).mean()),
            marginal_mean_window_energy=float(np.sum(abs(new)**2, axis=1).mean()),
            independent_QR=independent))
    assert scalar_error <= maximum
    rng = np.random.default_rng(620178)
    raw = rng.normal(size=operator.frames)
    observed = rng.normal(size=2*len(operator.starts)*len(operator.bins))
    left = float(real_rows(operator.apply(raw))@observed)
    right = float(raw@operator.adjoint(observed))
    adjoint_error = abs(left-right)/max(1., abs(left), abs(right))
    assert adjoint_error <= maximum
    columns = np.column_stack((raw, waves[0][1], waves[-1][1]))
    matrix = operator.apply(columns)
    column_error = max(float(abs(matrix[:, k]-operator.apply(columns[:, k])).max()) for k in range(3))
    assert column_error <= maximum
    first = operator.sample_matrix(0)
    lags = []
    hop = int(operator.starts[1]-operator.starts[0])
    for lag in (hop, round(operator.size/(2*hop))*hop, int(np.ceil(operator.size/hop))*hop):
        second = operator.sample_matrix(lag)
        overlap = max(0, operator.size-lag)
        cross = first[:, lag:]@second[:, :overlap].T if overlap else np.zeros((len(first), len(first)))
        correlation = float(np.sum(cross**2)/(variance**2*len(first)))
        lags.append(dict(lag_samples=lag, white_Gaussian_window_energy_correlation=correlation))
    return dict(passed=True, covariance=covariance, scalar_projection_maximum_error=scalar_error,
        adjoint_relative_error=adjoint_error, matrix_column_maximum_error=column_error,
        analytic_waveform_energies=energies, overlap_energy_correlations=lags,
        eigenvalue_minimum=float(operator.eigenvalues.min()), eigenvalue_maximum=float(operator.eigenvalues.max()),
        correlation_condition_number=float(operator.eigenvalues.max()/operator.eigenvalues.min()),
        maximum_observation_space_gain=float(1/np.sqrt(operator.eigenvalues.min())),
        per_real_row_white_noise_variance=variance,
        mean_window_white_noise_energy=variance*2*len(operator.bins),
        interwindow_whitening=False, phase_estimator_qualified=False,
        note='Exact marginal geometry and linear-operator controls only; no true-phase/RPM or real coloured-noise qualification')
