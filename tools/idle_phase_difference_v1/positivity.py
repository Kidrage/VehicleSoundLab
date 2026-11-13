"""Finite torus cover with a global second-derivative error bound."""
import numpy as np

EXPONENTS = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1],
                      [-1, 1, 0], [-1, 0, 1], [0, -1, 1]])
GRID_SIZE = 32
GUARD = 1e-10


def certify(coefficients):
    coefficient = np.asarray(coefficients)
    if coefficient.shape != (13, 4) or not np.isfinite(coefficient).all():
        raise ValueError('One finite expanded four-band law required')
    indices = np.indices((GRID_SIZE,)*3).reshape(3, -1).T
    theta = indices*(2*np.pi/GRID_SIZE)
    phase = theta @ EXPONENTS.T
    values = coefficient[0] + np.cos(phase) @ coefficient[1:7] + np.sin(phase) @ coefficient[7:13]
    index = values.argmin(axis=0)
    grid_min = values[index, np.arange(4)]
    radius = np.hypot(coefficient[1:7], coefficient[7:13])
    curvature = np.sum(radius*abs(EXPONENTS).sum(axis=1)[:, None]**2, axis=0)
    debt = .5*(np.pi/GRID_SIZE)**2*curvature
    lower = grid_min-debt-GUARD
    status = ['positive_bound' if low > 0 else 'negative_counterexample' if upper < -GUARD else 'UNKNOWN'
              for low, upper in zip(lower, grid_min)]
    return dict(grid_size=GRID_SIZE, points=len(theta), numerical_guard=GUARD,
                grid_minimum=grid_min.tolist(), grid_argmin_indices=indices[index].tolist(),
                curvature_bound=curvature.tolist(), covering_debt=debt.tolist(),
                global_lower_bound=lower.tolist(), status=status,
                all_bands_positive=all(s == 'positive_bound' for s in status))


def controls():
    outcomes = []
    for label, amount, minimum in [('positive_dependent', .45, .325), ('negative', .8, -.2)]:
        c = np.zeros((13, 4)); c[0] = 1; c[[1, 2, 4]] = amount
        for rotated in [False, True]:
            if rotated:
                phase = EXPONENTS @ np.array([.31, -.27, .62])
                a, b = c[1:7].copy(), c[7:13].copy()
                c[1:7] = a*np.cos(phase[:, None])-b*np.sin(phase[:, None])
                c[7:13] = a*np.sin(phase[:, None])+b*np.cos(phase[:, None])
            result = certify(c)
            assert max(result['global_lower_bound']) <= minimum+1e-12 <= min(result['grid_minimum'])+1e-12
            assert len(set(result['status'])) == 1
            assert result['status'][0] == ('positive_bound' if minimum > 0 else 'negative_counterexample')
            outcomes.append(dict(label=label, rotated=rotated, analytic_minimum=minimum, result=result,
                                 coefficients=c.tolist()))
    for label, amplitude, expected in [('constant', 0., 'positive_bound'), ('zero_minimum', -1., 'UNKNOWN')]:
        c = np.zeros((13, 4)); c[0] = 1; c[1] = amplitude
        result = certify(c)
        assert result['status'] == [expected]*4
        outcomes.append(dict(label=label, analytic_minimum=1+amplitude, result=result, coefficients=c.tolist()))
    return outcomes
