"""Exact graph solve with structured penalty, column blocks and no explicit Q."""
import numpy as np
from scipy import linalg
from .householder import Householder


def solve(forward,adjoint,prior,wave_metric,target,ledger,block=16):
    m,n=len(target),prior.size
    if target.ndim!=1 or wave_metric.shape!=(m,m) or block<1:
        raise ValueError('Invalid waveform dimensions or block size')
    ledger.add('wave_metric.input',wave_metric);ledger.add('penalty.K',prior.K);ledger.add('penalty.L',prior.L)
    ledger.snapshot('metric.before_root')
    # The supplied finite metric is consumed. Actual aliasing is reported;
    # overwrite_a=True by itself is not treated as evidence of reuse.
    Lw=linalg.cholesky(wave_metric,lower=True,overwrite_a=True,check_finite=False)
    metric_alias=bool(np.shares_memory(Lw,wave_metric));ledger.add('wave_metric.L',Lw)
    t=Lw.T@target;ledger.add('weighted_target',t)
    X=np.empty((m,n),order='F');ledger.add('weighted_synthesis',X)
    for first in range(0,n,block):
        last=min(n,first+block)
        raw=np.empty((m,last-first),order='F');ledger.add('source_block.'+str(first),raw)
        basis=np.zeros(n)
        for j in range(first,last):
            basis[j]=1;raw[:,j-first]=forward(basis);basis[j]=0
        X[:,first:last]=Lw.T@raw
    del raw,basis
    ledger.snapshot('weighted_synthesis.built')
    for first in range(0,m,block):
        last=min(m,first+block)
        X[first:last]=prior.inverse(X[first:last].T).T
    normA=float(np.sqrt(np.einsum('ij,ij->',X,X)+n))
    ledger.snapshot('weighted_synthesis.penalty_whitened')
    qr=Householder(X,ledger,'X_QR');del X
    F=qr.R;k=qr.k
    transformed=qr.apply(t,True);c=transformed[:k]
    D=np.empty((k+n,k),order='F');D[:k]=0;np.fill_diagonal(D[:k],1.);D[k:]=-F.T
    ledger.add('graph.input',D);ledger.snapshot('graph.before_QR')
    graph=Householder(D,ledger,'graph_QR');del D
    a=linalg.solve_triangular(graph.R.T,c,lower=True)
    coordinates=np.r_[a,np.zeros(n)]
    reduced=-graph.apply(coordinates)
    reduced[:k]=-linalg.solve_triangular(graph.R,a,lower=False)
    z=reduced[k:].copy();q=prior.inverse_transpose(z)
    residual_coordinates=-transformed.copy();residual_coordinates[:k]=reduced[:k]
    model=qr.apply(residual_coordinates)
    wave_model=linalg.solve_triangular(Lw.T,model,lower=False)
    # Compute complete actions through the original synthesis and node root,
    # not by declaring a projected normal zero.
    def apply_X(value):return Lw.T@forward(prior.inverse_transpose(value))
    def apply_XT(value):return prior.inverse(adjoint(Lw@value))
    direct=apply_X(z)-t
    normal=apply_XT(direct)+z;stable_normal=apply_XT(model)+z
    direct_norm=float(np.sqrt(direct@direct+z@z));model_norm=float(np.sqrt(model@model+z@z))
    direct_ratio=float(np.linalg.norm(normal)/max(normA*direct_norm,1e-300))
    stable_ratio=float(np.linalg.norm(stable_normal)/max(normA*model_norm,1e-300))
    backward=float(np.linalg.norm(direct-model)/max(np.linalg.norm(t),1e-300))
    for name,array in (('q',q),('z',z),('root.model',model),('wave.model',wave_model)):
        ledger.add(name,array)
    ledger.snapshot('solve.complete')
    # Reflectors are retained as diagnostics for known controls, never expanded
    # to Q. A later full run must declare serialization/storage lifetimes.
    values=dict(q=q,z=z,t=t,F=F,x_reflectors=qr.reflectors,x_tau=qr.tau,
        graph_reflectors=graph.reflectors,graph_tau=graph.tau,graph_R=graph.R,
        transformed_target=transformed,graph_coordinates=a,reduced_model_residual=reduced,
        root_model_residual=model,wave_model_residual=wave_model,
        direct_transformed_normal=normal,stable_root_normal=stable_normal,
        temporal_K=prior.K,temporal_L=prior.L)
    info=dict(method='structured_temporal_penalty_implicit_Householder_triangular_graph',
        waveform_rows=m,source_columns=n,retained_QR_directions=k,block=block,
        metric_root_shares_input=metric_alias,X_QR_alias=qr.alias,graph_QR_alias=graph.alias,
        explicit_Q_or_dense_packed_R_allocated_by_solver=False,
        complete_normal_uses_original_synthesis_adjoint=True,
        original_direct_whitened_normal_relative=direct_ratio,original_direct_whitened_normal_passed=direct_ratio<=1e-11,
        stable_root_normal_relative=stable_ratio,root_backward_discrepancy=backward,
        stable_root_guard_passed=bool(stable_ratio<=1e-11 and backward<=1e-11),
        augmented_root_Frobenius=normA,no_order_node_rank_rate_reduction=True)
    return values,info
