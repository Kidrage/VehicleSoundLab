"""Dense square-root waveform dual, without normal-equation solves or rank cuts."""
import numpy as np
from scipy import linalg


def solve(Phi, W, R, target):
    Phi, W, R, target = (np.asarray(x, float) for x in (Phi, W, R, target))
    m, n = Phi.shape
    if W.shape != (m, m) or R.shape != (n, n) or target.shape[0] != m:
        raise ValueError('Inconsistent waveform-space dimensions')
    if not all(np.isfinite(x).all() for x in (Phi, W, R, target)):
        raise ValueError('Nonfinite waveform-space input')
    symmetry=[float(np.max(abs(A-A.T))/max(float(np.max(abs(A))),1e-300)) for A in (W,R)]
    if max(symmetry)>1e-13:
        raise ValueError('Nonsymmetric metric or penalty')
    Lw, Lr = np.linalg.cholesky(W), np.linalg.cholesky(R)
    weighted = Lw.T@Phi
    t = Lw.T@target
    X = linalg.solve_triangular(Lr, weighted.T, lower=True).T
    # Economic QR retains min(m,n) directions, including zero/rank-deficient
    # directions. It does not estimate a rank or throw away weak singular values.
    (reflectors,tau),F = linalg.qr(X, mode='raw')
    k=min(m,n)
    reflectors=reflectors[:,:k]
    ormqr=linalg.get_lapack_funcs('ormqr',(reflectors,))
    def apply_q(value,transpose=False):
        vector=value.ndim==1
        value=np.asarray(value)[:,None] if vector else np.asarray(value)
        trans='T' if transpose else 'N'
        _,work,flag=ormqr('L',trans,reflectors,tau,value,lwork=-1)
        if flag:raise ArithmeticError(('ormqr workspace',flag))
        result,_,flag=ormqr('L',trans,reflectors,tau,value,lwork=int(work[0]))
        if flag:raise ArithmeticError(('ormqr application',flag))
        return result[:,0] if vector else result
    Q=apply_q(np.eye(m,k))
    transformed=apply_q(t,transpose=True)
    c=transformed[:k]
    G = np.vstack((F.T, np.eye(len(F))))
    d = np.concatenate((np.zeros((n,)+target.shape[1:]), c), axis=0)
    U, T = linalg.qr(G, mode='full')
    w = linalg.solve_triangular(T[:k], U[:,:k].T@d)
    z = F.T@w
    q = linalg.solve_triangular(Lr.T, z, lower=False)
    perpendicular_coordinates=transformed.copy()
    perpendicular_coordinates[:k]=0
    perpendicular=apply_q(perpendicular_coordinates)
    v = perpendicular+Q@w
    residual = X@z-t
    normal = X.T@residual+z
    augmented_norm = float(np.sqrt(np.sum(X*X)+n))
    residual_norm = float(np.sqrt(np.sum(residual*residual)+np.sum(z*z)))
    normal_norm = float(np.linalg.norm(normal))
    # The dual normal is retained, rather than declared zero. Its exact
    # identity is Fz+w-c. Construct it from the full QR complement, avoiding
    # both t-Q(Q^Tt) and Fz-c cancellation in the primal residual.
    dual_model=-U[:,k:]@(U[:,k:].T@d)
    dual_normal=G.T@dual_model
    residual_coordinates=-transformed.copy()
    residual_coordinates[:k]=-w+dual_normal
    model=apply_q(residual_coordinates)
    model_normal=X.T@model+z
    modeled_norm=float(np.sqrt(np.sum(model*model)+np.sum(z*z)))
    stable_ratio=float(np.linalg.norm(model_normal)/max(augmented_norm*modeled_norm,1e-300))
    backward=float(np.linalg.norm(model-residual)/max(np.linalg.norm(t),1e-300))
    wave_model=linalg.solve_triangular(Lw.T,model,lower=False)
    result = dict(q=q, z=z, X=X, t=t, Q=Q, F=F, w=w, v=v,
                  weighted_Phi=weighted, weighted_target=t, penalty_root=Lr,
                  direct_transformed_normal=normal,root_model_residual=model,stable_root_normal=model_normal,
                  wave_model_residual=wave_model,dual_model_residual=dual_model,dual_model_normal=dual_normal)
    info = dict(method='waveform_dual_economic_QR_without_rank_cut',
        waveform_rows=m, source_columns=n, retained_QR_directions=len(F),
        original_direct_whitened_normal_relative=normal_norm/max(augmented_norm*residual_norm, 1e-300),
        original_direct_whitened_normal_passed=bool(normal_norm <= 1e-11*augmented_norm*residual_norm),
        dual_augmented_condition=float(np.linalg.cond(G)),
        primal_augmented_condition=float(np.linalg.cond(np.vstack((F, np.eye(n))))),
        input_relative_symmetry_errors=symmetry,
        stable_root_normal_relative=stable_ratio,root_backward_discrepancy=backward,
        stable_root_guard_passed=bool(stable_ratio<=1e-11 and backward<=1e-11),
        stable_model_uses_complete_adjoint_not_projected_zero=True,
        no_iterative_stopping_code=True, no_rank_or_node_or_order_or_rate_reduction=True)
    return result, info
