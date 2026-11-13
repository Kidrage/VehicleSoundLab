"""Small explicit finite-ray controls with no engine/truth inputs."""
import numpy as np
from .direction import ray, construct


def controls():
    time = np.arange(5.); basis = np.array([[0., 0.], [.5, 0.], [1., 0.], [0., 1.], [0., 2.]])
    current = np.zeros(2); direction = np.array([.04, .03]); interior = np.ones(5, dtype=bool)
    vector, curve, value = construct(time, basis, current, direction, .18, interior, .01)
    errors = [abs(row['maximum_scale']-4.5) for row in value['cases']]
    assert value['both_targets_feasible'] and max(errors) <= 1e-12
    for row in value['cases']:
        candidate = current+row['sign']*row['target_scale']*vector
        assert abs(candidate).max() <= .18 and np.diff(time+basis@candidate).min() > 0
    steep = np.array([[0.], [-2.], [0.]])
    strict = ray(np.arange(3.), steep, np.zeros(1), np.array([.5]), 100.)
    assert strict['maximum_scale'] == 1. and not strict['limiting_constraint']['inclusive']
    assert np.diff(np.arange(3.)+steep[:, 0]*.25).min() > 0
    assert np.diff(np.arange(3.)+steep[:, 0]*.5).min() == 0
    try: construct(time, np.zeros((5, 2)), current, direction, .18, interior, .01)
    except ValueError as exc: zero_rejection = str(exc)
    else: raise AssertionError('Zero phase shape accepted')
    _, _, impossible = construct(time, basis, current, direction, .18, interior, 1.)
    assert not impossible['both_targets_feasible']
    return dict(passed=True, phase_box_maximum_scale_error=max(errors), strict_monotonic_limit=strict,
        zero_shape_rejected=zero_rejection, infeasible_target_not_reduced=True)
