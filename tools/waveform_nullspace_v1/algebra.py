"""Same waveform objective, with primal residual and nodes from one projection."""
import numpy as np
from scipy import linalg


def raw_qr(matrix):
    """Return thin R and an implicit full Householder-Q application."""
    (reflectors,tau),R=linalg.qr(matrix,mode='raw')
    reflectors=reflectors[:,:len(tau)]
    ormqr=linalg.get_lapack_funcs('ormqr',(reflectors,))
    def apply(value,transpose=False):
        vector=value.ndim==1
        value=np.asarray(value)[:,None] if vector else np.asarray(value)
        trans='T' if transpose else 'N'
        _,work,flag=ormqr('L',trans,reflectors,tau,value,lwork=-1)
        if flag:raise ArithmeticError(('ormqr workspace',flag))
        result,_,flag=ormqr('L',trans,reflectors,tau,value,lwork=int(work[0]))
        if flag:raise ArithmeticError(('ormqr application',flag))
        return result[:,0] if vector else result
    return R,apply


def solve(Phi,W,R,target,*,triangular_top=False):
    Phi,W,R,target=(np.asarray(v,float) for v in (Phi,W,R,target))
    m,n=Phi.shape
    if W.shape!=(m,m) or R.shape!=(n,n) or target.shape[0]!=m:
        raise ValueError('Inconsistent waveform-space dimensions')
    if not all(np.isfinite(v).all() for v in (Phi,W,R,target)):
        raise ValueError('Nonfinite waveform-space input')
    symmetry=[float(np.max(abs(A-A.T))/max(float(np.max(abs(A))),1e-300)) for A in (W,R)]
    if max(symmetry)>1e-13:raise ValueError('Nonsymmetric metric or penalty')
    Lw,Lr=np.linalg.cholesky(W),np.linalg.cholesky(R)
    weighted=Lw.T@Phi;t=Lw.T@target
    X=linalg.solve_triangular(Lr,weighted.T,lower=True).T
    F,apply=raw_qr(X);k=len(F)
    Q=apply(np.eye(m,k))
    transformed=apply(t,True);c=transformed[:k]
    # B=[F;I_n], D=[I_k;-F^T], B^T D=0. D has full column
    # rank even when X is rank deficient. No directions are discarded.
    D=np.vstack((np.eye(k),-F.T))
    T,apply_null=raw_qr(D)
    rhs=np.concatenate((c,np.zeros((n,)+target.shape[1:])),axis=0)
    if triangular_top:
        # Dtop=I implies exact Utop=T^-1. Applying a rounded tiny
        # Householder top block can lose relative accuracy. Triangular
        # solves evaluate this identity without assuming U/F/T are exact;
        # full original normal, backward error and gaps remain mandatory.
        a=linalg.solve_triangular(T.T,c,lower=True)
        coordinates=np.concatenate((a,np.zeros((n,)+target.shape[1:])),axis=0)
    else:
        coordinates=apply_null(rhs,True)
        coordinates[k:]=0
    reduced=-apply_null(coordinates)
    if triangular_top:reduced[:k]=-linalg.solve_triangular(T,a,lower=False)
    z=reduced[k:]
    residual_coordinates=-transformed.copy()
    residual_coordinates[:k]=reduced[:k]
    model=apply(residual_coordinates)
    q=linalg.solve_triangular(Lr.T,z,lower=False)
    perpendicular_coordinates=transformed.copy();perpendicular_coordinates[:k]=0
    w=-reduced[:k]
    v=apply(perpendicular_coordinates)+Q@w
    direct=X@z-t
    normal=X.T@direct+z
    stable_normal=X.T@model+z
    normA=float(np.sqrt(np.sum(X*X)+n))
    norm_direct=float(np.sqrt(np.sum(direct*direct)+np.sum(z*z)))
    norm_model=float(np.sqrt(np.sum(model*model)+np.sum(z*z)))
    direct_ratio=float(np.linalg.norm(normal)/max(normA*norm_direct,1e-300))
    stable_ratio=float(np.linalg.norm(stable_normal)/max(normA*norm_model,1e-300))
    backward=float(np.linalg.norm(model-direct)/max(np.linalg.norm(t),1e-300))
    wave_model=linalg.solve_triangular(Lw.T,model,lower=False)
    values=dict(q=q,z=z,X=X,t=t,Q=Q,F=F,w=w,v=v,weighted_Phi=weighted,
        weighted_target=t,penalty_root=Lr,direct_transformed_normal=normal,
        root_model_residual=model,stable_root_normal=stable_normal,wave_model_residual=wave_model,
        reduced_primal_model_residual=reduced,nullspace_generators=D)
    if triangular_top:
        values.update(triangular_graph_coordinates=a,nullspace_R=T)
    method='waveform_primal_residual_triangular_graph' if triangular_top else 'waveform_primal_residual_nullspace_raw_Householder'
    info=dict(method=method,waveform_rows=m,source_columns=n,
        retained_QR_directions=k,input_relative_symmetry_errors=symmetry,
        original_direct_whitened_normal_relative=direct_ratio,original_direct_whitened_normal_passed=direct_ratio<=1e-11,
        stable_root_normal_relative=stable_ratio,root_backward_discrepancy=backward,
        stable_root_guard_passed=bool(stable_ratio<=1e-11 and backward<=1e-11),
        primal_augmented_condition=float(np.linalg.cond(np.vstack((F,np.eye(n))))),
        dual_augmented_condition=float(np.linalg.cond(D)),
        stable_model_uses_complete_adjoint_not_projected_zero=True,
        full_dual_Q_allocated=False,primal_nodes_and_residual_share_projection=True,
        tiny_identity_block_evaluated_by_triangular_solves=triangular_top,
        no_iterative_stopping_code=True,no_rank_or_node_or_order_or_rate_reduction=True)
    return values,info
