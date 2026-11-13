"""Unconstrained fixed linear response after profiling all nuisance columns."""
import numpy as np
from scipy.linalg import svd


def profile(matrix, phase_indices, rhs):
    indices = np.asarray(phase_indices, dtype=int)
    nuisance_indices = np.setdiff1d(np.arange(matrix.shape[1]), indices)
    nuisance = matrix[:, nuisance_indices]; common = matrix[:, indices]
    cutoff = np.finfo(float).eps*max(matrix.shape)*np.linalg.norm(matrix, 'fro')
    u, s, vt = svd(nuisance, full_matrices=False, lapack_driver='gesdd')
    nuisance_rank = int(np.sum(s > cutoff))
    if nuisance_rank != nuisance.shape[1]:
        raise ValueError(f'Nuisance rank unresolved: {nuisance_rank}/{nuisance.shape[1]}, cutoff={cutoff}')
    residualized = np.column_stack((common, rhs))
    residualized -= u@(u.T@residualized)
    phase = residualized[:, :len(indices)]; targets = residualized[:, len(indices):]
    pu, ps, pvt = svd(phase, full_matrices=False, lapack_driver='gesdd')
    phase_rank = int(np.sum(ps > cutoff))
    if phase_rank != len(indices):
        raise ValueError(f'Phase rank unresolved: {phase_rank}/{len(indices)}, cutoff={cutoff}')
    changes = -(pvt.T/ps[None, :])@(pu.T@targets)
    free = (vt.T/s[None, :])@(u.T@(-rhs-common@changes))
    complete = np.zeros((matrix.shape[1], rhs.shape[1]))
    complete[indices] = changes; complete[nuisance_indices] = free
    fitted = matrix@complete+rhs
    score = phase.T@targets
    normal = matrix.T@fitted
    normal_relative = np.linalg.norm(normal, axis=0)/np.maximum(
        np.linalg.norm(matrix, 'fro')*np.linalg.norm(rhs, axis=0), 1e-30)
    return dict(phase_changes=changes, all_changes=complete, profiled_score=score,
        nuisance_singular=s, phase_singular=ps, cutoff=cutoff,
        nuisance_rank=nuisance_rank, phase_rank=phase_rank,
        phase_condition=float(ps[0]/ps[-1]), nuisance_condition=float(s[0]/s[-1]),
        relative_normal_equations=normal_relative,
        profiled_rhs_norm=np.linalg.norm(targets, axis=0),
        fitted_residual_norm=np.linalg.norm(fitted, axis=0))
