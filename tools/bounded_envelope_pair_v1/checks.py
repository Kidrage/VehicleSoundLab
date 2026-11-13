"""Closed-form cone faces independently qualify the new finite compensation use."""
import numpy as np
from .solve import fit


def controls(settings):
    cases = [
        ('interior', [.4, .4], [.4, .4]),
        ('lower_face', [.4, 0.], [.4/(1+.75**2), .75*.4/(1+.75**2)]),
        ('upper_face', [0., .8], [1.25*.8/(1+1.25**2), 1.25**2*.8/(1+1.25**2)]),
        ('cap', [2., 2.], [1., 1.25]),
        ('zero', [-.4, -.8], [0., 0.])]
    rows = []
    for name, target, expected in cases:
        values, result = fit(np.eye(2), np.asarray(target), np.array([[.5, .5]]),
                             .25, np.ones(1), settings)
        error = float(abs(values.ravel()-expected).max())
        passed = bool(result['certificate']['success'] and error <= 1e-7)
        rows.append(dict(id=name, passed=passed, maximum_control_error=error, result=result))
    return dict(passed=all(row['passed'] for row in rows), cases=rows,
        known_closed_form_controls=True, phase_estimator_qualified=False)
