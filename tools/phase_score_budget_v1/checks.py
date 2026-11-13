"""Small independent linear controls, no fixture phase or model inputs."""
import numpy as np
from .projection import profile


def rotate(rows, angle):
    half = len(rows)//2; c, s = np.cos(angle), np.sin(angle)
    return np.concatenate((c*rows[:half]-s*rows[half:], s*rows[:half]+c*rows[half:]))


def controls():
    rng = np.random.default_rng(741602)
    matrix = rng.normal(size=(12, 5)); indices = [1, 3]; nuisance = [0, 2, 4]
    changes = rng.normal(0, .02, size=(5, 3))
    trial = rng.normal(0, .01, size=(12, 3))
    # Small well-conditioned independent normal equations are an oracle here only.
    orthogonal = trial-matrix@np.linalg.solve(matrix.T@matrix, matrix.T@trial)
    rhs = -matrix@changes+orthogonal
    rhs = np.column_stack((rhs, rhs.sum(axis=1), np.zeros(12)))
    value = profile(matrix, indices, rhs)
    explicit = -np.linalg.solve(matrix.T@matrix, matrix.T@rhs)
    errors = dict(known=float(abs(value['all_changes'][:, :3]-changes).max()),
        normal_equation_oracle=float(abs(value['all_changes']-explicit).max()),
        zero=float(abs(value['all_changes'][:, -1]).max()),
        additivity=float(abs(value['all_changes'][:, :3].sum(axis=1)-value['all_changes'][:, 3]).max()))
    rotated = profile(rotate(matrix, .37), indices, rotate(rhs, .37))
    errors['rotation'] = float(abs(rotated['all_changes']-value['all_changes']).max())
    transformed = matrix.copy()
    coordinate = np.array([[1., .2, -.1], [0., .8, .1], [.1, 0., 1.2]])
    transformed[:, nuisance] = matrix[:, nuisance]@coordinate
    new = profile(transformed, indices, rhs)
    errors['nuisance_coordinate'] = float(abs(new['phase_changes']-value['phase_changes']).max())
    degenerate = matrix.copy(); degenerate[:, indices[0]] = degenerate[:, nuisance[0]]
    try:
        profile(degenerate, indices, rhs)
    except ValueError as exc:
        rejected = str(exc)
    else:
        raise AssertionError('Degenerate phase source was accepted')
    assert max(errors.values()) <= 1e-12, errors
    return dict(passed=True, errors=errors, known_matrix_condition=float(np.linalg.cond(matrix)),
        expected_degeneracy_rejection=rejected, threshold_rule='eps*max(matrix.shape)*FrobeniusNorm(matrix)',
        limits=['Linear diagnostic operator controls only; not a phase estimator or confidence model'])
