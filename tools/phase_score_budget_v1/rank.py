"""Numerical geometry inspection only; never invert weak phase directions."""
import numpy as np
from scipy.linalg import svd


def inspect(matrix, indices):
    indices = np.asarray(indices, dtype=int)
    nuisance_indices = np.setdiff1d(np.arange(matrix.shape[1]), indices)
    nuisance, phase = matrix[:, nuisance_indices], matrix[:, indices]
    cutoff = np.finfo(float).eps*max(matrix.shape)*np.linalg.norm(matrix, 'fro')
    u, singular, right = svd(nuisance, full_matrices=False, lapack_driver='gesdd')
    rank = int(np.sum(singular > cutoff)); supported = u[:, :rank]
    projected = phase-supported@(supported.T@phase)
    _, phase_singular, phase_right = svd(projected, full_matrices=False, lapack_driver='gesdd')
    full_singular = svd(matrix, full_matrices=False, compute_uv=False, lapack_driver='gesdd')
    null_direction = right[-1]
    phase_direction = phase_right[-1]
    return dict(cutoff=float(cutoff), nuisance_rank=rank,
        conditional_phase_rank=int(np.sum(phase_singular > cutoff)),
        full_rank=int(np.sum(full_singular > cutoff)),
        nuisance_singular=singular, phase_singular=phase_singular, full_singular=full_singular,
        weakest_nuisance_direction=null_direction, weakest_phase_direction=phase_direction,
        weakest_nuisance_norm=float(np.linalg.norm(nuisance@null_direction)),
        weakest_conditional_phase_norm=float(np.linalg.norm(projected@phase_direction)),
        conditional_orthogonality=float(np.linalg.norm(supported.T@projected)),
        matrix_frobenius=float(np.linalg.norm(matrix, 'fro')),
        phase_frobenius=float(np.linalg.norm(phase, 'fro')))


def controls():
    # Orthogonal integer columns make all ranks available without an SVD oracle.
    matrix = np.eye(8)[:, :5]; indices = [1, 3]
    cases = [('full', matrix, (3, 2, 5))]
    duplicate = matrix.copy(); duplicate[:, 1] = duplicate[:, 0]
    cases.append(('phase_nuisance_duplicate', duplicate, (3, 1, 4)))
    zero_nuisance = matrix.copy(); zero_nuisance[:, [0, 2, 4]] = 0
    cases.append(('zero_nuisance', zero_nuisance, (0, 2, 2)))
    zero_phase = matrix.copy(); zero_phase[:, indices] = 0
    cases.append(('zero_phase', zero_phase, (3, 0, 3)))
    results = []
    for label, value, expected in cases:
        result = inspect(value, indices)
        actual = tuple(result[key] for key in ('nuisance_rank', 'conditional_phase_rank', 'full_rank'))
        assert actual == expected
        assert result['conditional_orthogonality'] <= 1e-12
        results.append(dict(id=label, expected=list(expected), observed=list(actual)))
    return dict(passed=True, cases=results, no_response_inverse=True)
