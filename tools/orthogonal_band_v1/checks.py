"""Finite-record orthogonality, direct quadrature and explicit leakage controls."""
import numpy as np
from aperture_model_v1.forward import real_rows
from .operator import OrthogonalBand


def controls(plan):
    small = dict(plan, samples_per_cycle=16, cycles=4, projection_cycles=2,
        observed_order_range=[1, 3])
    op = OrthogonalBand(64, small); t = np.arange(64)/16
    matrix = op.factor*np.exp(-2j*np.pi*op.orders[:, None]*t)
    real_matrix = real_rows(matrix); target = op.row_variance*np.eye(len(real_matrix))
    covariance_error = float(np.max(abs(real_matrix@real_matrix.T-target)))
    assert covariance_error < 1e-12
    rng = np.random.default_rng(671935); columns = rng.normal(size=(64, 4))
    forward_error = float(abs(real_rows(op.apply(columns))-real_matrix@columns).max())
    pull = rng.normal(size=(len(real_matrix), 4))
    adjoint_error = float(abs(op.adjoint(pull)-real_matrix.T@pull).max())
    assert max(forward_error, adjoint_error) < 1e-12
    assert np.linalg.norm(real_rows(op.apply(columns))) <= np.sqrt(op.row_variance)*np.linalg.norm(columns)+1e-12
    assert np.count_nonzero(op.apply(np.zeros(64))) == 0
    for order, expected in ((2., 1.), (4., 0.)):
        wave = np.cos(2*np.pi*order*t+.31)
        fraction = float(np.sum(abs(op.apply(wave))**2)/(op.row_variance*np.sum(wave**2)))
        assert abs(fraction-expected) < 1e-12
    frames = round(plan['cycles']*plan['samples_per_cycle']); time = np.arange(frames)/plan['samples_per_cycle']
    actual = OrthogonalBand(frames, plan); observations = []
    epsilon = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2)
    waves = [(f'tone_{order}', .2*np.cos(2*np.pi*order*time+.31)) for order in (3., 3.1, 8.37, 9.13, 10., 15.)]
    for label in ('rapid_common', 'occluded_partial', 'local_phase'):
        wave = np.zeros_like(time)
        for k, order in enumerate((2., 3., 5., 7.)):
            amplitude = .03*(1+.08*np.sin(2*np.pi*.023*time+.2*k))
            if label == 'occluded_partial' and k == 1: amplitude *= 1-.95*np.exp(-((time-20)/.8)**4)
            angle = 2*np.pi*order*(time+epsilon)+.17*k
            if label == 'local_phase' and k == 2: angle += .6*np.sin(2*np.pi*.17*time)
            wave += amplitude*np.cos(angle)
        waves.append((label, wave))
    maximum = 0.
    for label, wave in waves:
        direct = np.array([actual.factor*np.sum(wave*(np.cos(2*np.pi*order*time)-1j*np.sin(2*np.pi*order*time))) for order in actual.orders])
        values = actual.apply(wave); error = float(abs(direct-values).max()); maximum = max(maximum, error)
        energy = float(np.sum(abs(values)**2)); bound = float(actual.row_variance*np.sum(wave**2))
        assert energy <= bound+1e-12
        observations.append(dict(id=label, direct_maximum_error=error, projection_fraction=energy/bound))
    assert maximum < plan['rules']['maximum_forward_check_error']
    return dict(passed=True, explicit_covariance_maximum_error=covariance_error,
        small_forward_maximum_error=forward_error, small_adjoint_maximum_error=adjoint_error,
        scalar_forward_maximum_error=maximum, known_waveforms=observations,
        original_frames=frames, original_positive_bins=len(actual.bins),
        original_real_rows=2*len(actual.bins), row_white_variance=actual.row_variance,
        covariance='exact variance*I for source white noise', full_record_boundary_leakage_not_eliminated=True)
