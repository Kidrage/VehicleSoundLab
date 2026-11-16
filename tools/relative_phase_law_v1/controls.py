"""Exact known laws and finite-row invariants; no real compiler calls."""
import numpy as np
from .measure import assess, lag_covariance, stationary


def controls(check):
    width = 8
    b = np.eye(width)
    rho = np.linspace(-.6, .8, width)
    model = dict(basis=b, rho=rho, residual_std=np.zeros(width), residual_rho=np.zeros(width))
    for lag in (0, 1, 2, 4, 8):
        actual, _, _ = stationary(model, lag)
        check('known_independent_AR1_'+str(lag), actual, np.diag(rho**lag), 1.)
    # Same unit normal marginals / C0 and same diagonal lag1, but different
    # directed cross-lag and lag2. A rank increase in independent AR1 cannot fix it.
    theta, radius = .6, .8
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    a = radius*rotation
    scalar = np.eye(2)*radius*np.cos(theta)
    check('rotation_stationary_Lyapunov', a@a.T+(1-radius**2)*np.eye(2), np.eye(2), 1.)
    check('scalar_stationary_Lyapunov', scalar@scalar.T+(1-(radius*np.cos(theta))**2)*np.eye(2), np.eye(2), 1.)
    check('same_C0', np.eye(2), np.eye(2), 1.)
    check('same_diagonal_lag1', np.diag(a), np.diag(scalar), 1.)
    assert np.linalg.norm(a-a.T) > .5
    assert np.linalg.norm(a@a-scalar@scalar) > .2
    for lag in (1, 2, 4, 8):
        expected = radius**lag*np.array([[np.cos(lag*theta), -np.sin(lag*theta)],
            [np.sin(lag*theta), np.cos(lag*theta)]])
        check('known_rotation_power_'+str(lag), np.linalg.matrix_power(a, lag), expected, 1.)
    n = np.arange(128)
    x = np.column_stack([np.cos(2*np.pi*(j+1)*n/128+.13*j) for j in range(width)])
    y = .2*np.column_stack([np.sin(2*np.pi*(j+9)*n/128) for j in range(width)])
    saved = dict(scores=x+y, pc=x, residual=y)
    arrays, rows, group_rows, meta = assess(model, saved, (0, 1, 2, 4, 8))
    for lag in (0, 1, 2, 4, 8):
        c = lag_covariance(x+y, lag)
        check('known_reversal_'+str(lag), lag_covariance((x+y)[::-1], lag), c.T, 1.)
        check('known_component_closure_'+str(lag), arrays[f'lag{lag}_error_components'].sum(axis=0),
            arrays[f'lag{lag}_model']-c, 1.)
        skew = (c-c.T)/2
        difference = arrays[f'lag{lag}_model']-c
        symmetric = (difference+difference.T)/2
        check('known_skew_lower_bound_'+str(lag), np.sum(difference**2),
            np.sum(symmetric**2)+np.sum(skew**2), max(float(np.sum(difference**2)), 1.))
    perm = np.random.Generator(np.random.PCG64(17)).permutation(len(x))
    check('row_permutation_C0_exact', lag_covariance((x+y)[perm], 0), lag_covariance(x+y, 0), 1.)
    assert np.linalg.norm(lag_covariance((x+y)[perm], 1)-lag_covariance(x+y, 1)) > .3
    quiet = dict(saved, scores=saved['scores'].copy(), pc=saved['pc'].copy(), residual=saved['residual'].copy())
    for value in quiet.values(): value[:, -1] = 0
    quiet_model = dict(model, basis=b.copy())
    quiet_model['basis'][-1] = 0
    silent, _, _, _ = assess(quiet_model, quiet, (0, 1))
    assert np.count_nonzero(silent['lag1_observed'][-1]) == 0
    assert np.count_nonzero(silent['lag1_model'][-1]) == 0
    zeros = dict(scores=np.zeros_like(x), pc=np.zeros_like(x), residual=np.zeros_like(x))
    zero_model = dict(model, basis=np.zeros_like(b))
    zero, _, _, _ = assess(zero_model, zeros, (0, 1))
    assert not np.count_nonzero(zero['lag1_model']) and not np.count_nonzero(zero['lag1_observed'])
    arrays.update(known_rotation_A=a, known_scalar_A=scalar, known_source_rows=x+y,
        known_permutation=perm, known_silent_observed=silent['lag1_observed'],
        known_silent_model=silent['lag1_model'], known_zero_observed=zero['lag1_observed'],
        known_zero_model=zero['lag1_model'])
    return arrays, rows, group_rows, meta, dict(controls=8, known_before_actual=True,
        all_passed=True, same_static_and_diagonal_lag1_do_not_determine_temporal_law=True,
        empirical_skew_not_proof_of_physical_direction=True)
