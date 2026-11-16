"""Minimum quadratic prior with explicit relative error balls for every block.

Dense known-only prototype: bounded dimensions, no data files, oscillator
timeline, runtime host, or change to the existing declared C1 objective.
"""
import numpy as np
from scipy.linalg import cho_factor,cho_solve,norm as stable_norm


def assess_groups(residual,target,groups):
    """Zero targets require exact zero residual; no relative denominator exists.

    The mixed diagnostic retains absolute errors for zero targets, but the
    strict gate must never interpret those values as relative errors.
    """
    target_norms=np.array([stable_norm(target[g]) for g in groups])
    absolute=np.array([stable_norm(residual[g]) for g in groups])
    ratios=absolute.copy();positive=target_norms>0
    ratios[positive]/=target_norms[positive]
    exact_zero=np.array([np.all(residual[g]==0.) for g in groups])
    passed=np.where(positive,ratios<.02,exact_zero)
    return target_norms,absolute,ratios,passed


def solve(design,target,prior,groups,*,epsilon=.015,iterations=10000,tolerance=1e-10):
    d,y,r=map(np.asarray,(design,target,prior))
    if (not isinstance(iterations,(int,np.integer)) or isinstance(iterations,(bool,np.bool_))
        or not isinstance(epsilon,(int,float,np.integer,np.floating))
        or not isinstance(tolerance,(int,float,np.integer,np.floating))
        or not np.isfinite(epsilon) or not np.isfinite(tolerance)):
        raise ValueError('Finite real tolerances and an integer iteration limit required')
    if (d.ndim!=2 or not 1<=d.shape[1]<=32 or not 1<=len(d)<=256
        or y.shape!=(len(d),) or r.shape!=(d.shape[1],d.shape[1])
        or any(np.iscomplexobj(v) or not np.isfinite(v).all() for v in (d,y,r))
        or not 0<epsilon<.02 or not 1<=iterations<=20000 or tolerance<=0):
        raise ValueError('Finite small real known system and strict fidelity margin required')
    if not np.allclose(r,r.T,atol=1e-14,rtol=0):raise ValueError('Symmetric positive prior required')
    cho_factor(r,lower=True)
    ids=[np.asarray(g) for g in groups]
    if not ids or any(g.ndim!=1 or len(g)==0 for g in ids):raise ValueError('Nonempty row partition required')
    if any(g.dtype.kind not in 'iu' for g in ids):raise ValueError('Integer row indices required without coercion')
    if not np.array_equal(np.sort(np.concatenate(ids)),np.arange(len(d))):raise ValueError('All rows must appear once')
    ids=[g.astype(np.intp) for g in ids]
    scales=np.ones(len(d));radii=[]
    for g in ids:
        norm=float(stable_norm(y[g]));scales[g]=norm if norm else 1.
        radii.append(epsilon if norm else 0.)
    # Exact positive rescaling of each constraint; no weak band is dropped.
    a,b=d/scales[:,None],y/scales
    system=cho_factor(r+a.T@a,lower=True)
    def project(value):
        out=value.copy()
        for g,radius in zip(ids,radii):
            norm=float(np.linalg.norm(out[g]))
            if norm>radius:out[g]*=radius/norm
        return out
    q=np.zeros(d.shape[1]);v=project(-b);u=np.zeros(len(d));history=[]
    for step in range(iterations):
        q=cho_solve(system,a.T@(b+v-u))
        residual=a@q-b;previous=v;v=project(residual+u);u+=residual-v
        primal=float(np.linalg.norm(residual-v));dual=float(np.linalg.norm(a.T@(v-previous)))
        if step==0 or step==iterations-1 or max(primal,dual)<=tolerance:history.append((step+1,primal,dual))
        if max(primal,dual)<=tolerance:break
    target_norms,absolute,relative,passed=assess_groups(d@q-y,y,ids)
    stationarity=float(np.linalg.norm(r@q+a.T@u))
    primal_cost=float(.5*q@r@q)
    inverse=cho_solve(cho_factor(r,lower=True),a.T@u)
    dual_bound=float(-.5*(a.T@u)@inverse-u@b-sum(radius*np.linalg.norm(u[g]) for g,radius in zip(ids,radii)))
    return dict(coefficients=q,normalized_dual=u,row_scales=scales,
        relative_or_zero_target_absolute_errors=np.array(relative),iterations=step+1,
        group_target_norms=target_norms,group_absolute_errors=absolute,
        group_original_strict_fidelity_passed=passed,
        primal_residual=primal,dual_residual=dual,stationarity=stationarity,
        primal_cost=primal_cost,dual_lower_bound=dual_bound,nominal_gap=primal_cost-dual_bound,
        converged=bool(max(primal,dual)<=tolerance),
        original_strict_fidelity_passed=bool(passed.all()),history=np.asarray(history),
        no_vehicle_or_large_scale_or_realtime_or_naturalness_qualification=True)
