"""Gaussian mixture + linear independent-innovation budget, with no audio rendering."""
import numpy as np
from idle_wave_budget_v1.moments import pooled, TERMS

PAIRS = [(b, c) for b in range(4) for c in range(b, 4)]
AUTO = [0, 4, 7, 9]


def summarize(main, covariance, operator):
    mean = main.mean(axis=0)
    variance = ((main-mean)**2).mean(axis=0)+np.diag(covariance.mean(axis=0))
    terms = []; cumulant = []
    for b, c in PAIRS:
        row = pooled(main[:, b], main[:, c], covariance[:, b, b], covariance[:, c, c],
                     covariance[:, b, c], np.zeros(len(main)))
        terms.append([row['terms'][key] for key in TERMS]); cumulant.append(row['cumulant'])
    denom = np.array([variance[b]*variance[c] for b, c in PAIRS])
    matrix = np.array([operator[:, b, c, :].mean(axis=0) for b, c in PAIRS])
    return dict(variance=variance, terms=np.asarray(terms), gaussian=np.asarray(cumulant),
                operator=matrix, denominator=denom, mean_power=np.mean(main*main, axis=0)+np.diag(covariance.mean(axis=0)))


def allocate(state, source):
    target = source*state['denominator']
    debt = target-state['gaussian']; A = state['operator'][AUTO]
    row_scale = state['denominator'][AUTO]
    matrix = A/row_scale[:, None]
    coordinate = np.linalg.norm(matrix, axis=0)
    if np.any(coordinate == 0): return dict(status='rank_deficient_UNKNOWN', generative=False)
    normalized = matrix/coordinate
    singular = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.count_nonzero(singular > np.finfo(float).eps*4*singular[0]))
    result = dict(rank=rank, singular=singular.tolist(), debt=debt.tolist(), coordinate=coordinate.tolist())
    if rank != 4: return dict(result, status='rank_deficient_UNKNOWN', generative=False)
    kappa = np.linalg.solve(normalized, debt[AUTO]/row_scale)/coordinate
    valid = bool(np.all(kappa >= 0))
    result.update(status='positive_allocation' if valid else 'negative_solution_NOT_generative', generative=valid,
                  kappa=kappa.tolist(), probability=(3/(kappa+3)).tolist() if valid else None,
                  normalized_solve_residual=float(abs(matrix@kappa-debt[AUTO]/row_scale).max()))
    return result


def prediction(state, kappa):
    return (state['gaussian']+state['operator']@kappa)/state['denominator']
