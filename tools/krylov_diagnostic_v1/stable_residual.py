"""Complete-QR residual and full adjoint, retaining outside-subspace gradient."""
import numpy as np
from scipy import linalg


def estimate(H, U, V, rhs, backward, direct_forward):
    rows, columns = H.shape
    if U.shape[1] != rows or V.shape[1] != columns or rows < columns:
        raise ValueError('Inconsistent square-root projection dimensions')
    target = np.zeros(rows)
    target[0] = np.linalg.norm(rhs)
    Q, R = linalg.qr(H, mode='full')
    if columns:
        y = linalg.solve_triangular(R[:columns], Q[:, :columns].T@target)
    else:
        y = np.zeros(0)
    complement = Q[:, columns:]
    coefficients = -complement@(complement.T@target)
    z = V@y
    residual = U@coefficients
    normal = backward(residual)
    projected_normal = V@(V.T@normal)
    outside = normal-projected_normal
    direct_residual = direct_forward(z)-rhs
    direct_normal = backward(direct_residual)
    nr = float(np.linalg.norm(coefficients))
    ng = float(np.linalg.norm(normal))
    anorm = float(np.linalg.norm(H))
    discrepancy = float(np.linalg.norm(direct_residual-residual))
    info = dict(stable_residual_norm=nr, stable_normal_norm=ng,
        stable_normal_relative=ng/max(anorm*nr, 1e-300),
        outside_subspace_normal_norm=float(np.linalg.norm(outside)),
        projected_only_normal_norm=float(np.linalg.norm(H.T@coefficients)),
        direct_residual_norm=float(np.linalg.norm(direct_residual)),
        direct_normal_norm=float(np.linalg.norm(direct_normal)),
        direct_normal_relative=float(np.linalg.norm(direct_normal))/max(anorm*np.linalg.norm(direct_residual), 1e-300),
        direct_model_discrepancy=discrepancy,
        relative_backward_discrepancy=discrepancy/max(float(np.linalg.norm(rhs)), 1e-300),
        projected_Frobenius_estimate=anorm, no_interval_or_full_normal_bound_claim=True)
    capture = dict(y=y, z=z, residual_coefficients=coefficients, stable_residual=residual,
        stable_normal=normal, outside_normal=outside, direct_residual=direct_residual, direct_normal=direct_normal)
    return capture, info
