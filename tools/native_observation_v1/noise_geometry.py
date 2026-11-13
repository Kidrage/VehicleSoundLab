"""Exact covariance of periodic-Hann real-sample projections under white noise."""
import numpy as np


def sample_rows(operator, start):
    local = np.arange(operator.size)
    order = operator.bins/operator.size
    complex_rows = (2/operator.window.sum())*operator.window[None, :]*np.exp(
        -2j*np.pi*order[:, None]*(local[None, :]+start))
    return np.vstack((complex_rows.real, complex_rows.imag)), complex_rows


def geometry(operator, hop):
    real, complex_rows = sample_rows(operator, 0)
    covariance = real@real.T
    hermitian = complex_rows@complex_rows.conj().T
    pseudo = complex_rows@complex_rows.T
    differences = operator.bins[:, None]-operator.bins[None, :]
    expected = np.zeros(differences.shape)
    factor = 4*operator.size/operator.window.sum()**2
    expected[differences == 0] = factor*.375
    expected[abs(differences) == 1] = -factor*.25
    expected[abs(differences) == 2] = factor*.0625
    maximum = float(abs(hermitian-expected).max())
    assert maximum < 1e-12 and abs(pseudo).max() < 1e-12
    trace = float(np.trace(covariance))
    square_trace = float(np.sum(covariance**2))
    dof = trace**2/square_trace
    normalized = hermitian/np.sqrt(hermitian.diagonal().real[:, None]*hermitian.diagonal().real[None, :])
    pairs = []
    lags = [hop, round(operator.size/(2*hop))*hop, int(np.ceil(operator.size/hop))*hop]
    for lag in lags:
        second, _ = sample_rows(operator, lag)
        overlap = max(0, operator.size-lag)
        cross = real[:, lag:]@second[:, :overlap].T if overlap else np.zeros_like(covariance)
        # For real white Gaussian n, Cov(||An||²,||Bn||²)=2||AB'||_F².
        energy_correlation = float(np.sum(cross**2)/square_trace)
        if not overlap:
            assert energy_correlation == 0
        pairs.append(dict(lag_samples=int(lag), overlap_samples=int(overlap),
            white_Gaussian_window_energy_correlation=energy_correlation))
    return dict(bins=len(operator.bins), real_rows_per_window=len(real),
        exact_Hann_hermitian_covariance_maximum_error=maximum,
        exact_pseudo_covariance_maximum=float(abs(pseudo).max()),
        native_adjacent_complex_noise_correlation=-2/3,
        native_two_bin_complex_noise_correlation=1/6,
        adjacent_selected_bin_correlation=float(normalized[0, 1].real),
        unit_source_variance_projection_energy=trace,
        unit_source_variance_Gaussian_energy_variance=2*square_trace,
        energy_variance_equivalent_real_degrees_of_freedom=float(dof),
        temporal_energy_correlations=pairs,
        source_white_noise_assumed=True, real_noise_calibrated=False,
        phase_information_rank=False, calibrated_latent_uncertainty=False)
