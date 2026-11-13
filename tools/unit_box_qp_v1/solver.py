"""Equivalent unit-trust coordinates, with certificates in ORIGINAL units."""
import numpy as np
import scipy.sparse as sp
import clarabel
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish
from joint_trust_v1.osqp_backend import linear_system


def metrics(gram, gradient, matrix, lower, upper, step, z, scale):
    rows,bounds,high,low=inequalities(matrix,lower,upper)
    y=np.zeros(matrix.shape[0]);y[high]+=z[:len(high)];y[low]-=z[len(high):]
    normal=(gram+gram.T)/(2*scale);observed=matrix@step
    primal=float(max(0.,np.max(lower-observed),np.max(observed-upper)))
    dual=float(abs(normal@step+gradient/scale+matrix.T@y).max())
    sign=float(max(0.,-z.min()));comp=float(abs(z*(bounds-rows@step)).max())
    return y,dict(normalized_dual_stationarity=dual,constraint_violation=primal,
        inequality_dual_sign_violation=sign,maximum_complementarity=comp,
        normalized_duality_gap=float(z@(bounds-rows@step)),
        original_objective_dual_stationarity=dual*scale,objective_scale=scale,
        objective=float(.5*step@gram@step+gradient@step))


def certified(evidence,settings):
    return bool(evidence['constraint_violation']<=settings['maximum_primal_violation']
        and evidence['normalized_dual_stationarity']<=settings['maximum_normalized_stationarity']
        and evidence['inequality_dual_sign_violation']<=settings['maximum_primal_violation']
        and evidence['maximum_complementarity']<=settings['maximum_complementarity'])


def solve_system(gram,gradient,weighted,rhs,matrix,lower,upper,radius,settings):
    if not np.isfinite(radius) or radius<=0:raise ValueError('Positive finite trust radius required')
    maximum=float(abs(gradient).max());scale=maximum if maximum>0 else max(float(abs(gram).max()),1.)
    factor=np.linalg.qr(weighted,mode='r');n=len(gradient);m=factor.shape[0]
    assert np.linalg.norm(factor.T@factor-gram)<=1e-12*max(1.,np.linalg.norm(gram))
    dense=matrix.toarray();finite_lo=np.where(np.isfinite(lower),abs(lower),0.)
    finite_hi=np.where(np.isfinite(upper),abs(upper),0.)
    row_scale=np.maximum.reduce((abs(dense*radius).max(axis=1),finite_lo,finite_hi))
    row_scale=np.where(row_scale>0,row_scale,1.)
    unit_matrix=sp.diags(radius/row_scale)@matrix
    unit_lower,unit_upper=lower/row_scale,upper/row_scale
    rows,bounds,high,low=inequalities(unit_matrix,unit_lower,unit_upper)
    root=factor*np.sqrt(radius/scale)
    equality=sp.hstack((sp.csc_matrix(root),-sp.eye(m,format='csc')),format='csc')
    inequality=sp.hstack((rows,sp.csc_matrix((len(bounds),m))),format='csc')
    lifted=sp.vstack((equality,inequality),format='csc');lifted_bounds=np.r_[np.zeros(m),bounds]
    p=sp.diags(np.r_[np.zeros(n),np.ones(m)],format='csc')
    config=clarabel.DefaultSettings();config.verbose=False
    config.max_iter=settings['ipm_max_iterations'];config.max_threads=settings['ipm_max_threads']
    config.tol_gap_abs=config.tol_gap_rel=config.tol_feas=settings['ipm_tolerance']
    solver=clarabel.DefaultSolver(p,np.r_[gradient/scale,np.zeros(m)],lifted,lifted_bounds,
        [clarabel.ZeroConeT(m),clarabel.NonnegativeConeT(len(bounds))],config)
    solution=solver.solve();t=np.asarray(solution.x[:n]);aux=np.asarray(solution.x[n:])
    equality_dual=np.asarray(solution.z[:m]);unit_z=np.asarray(solution.z[m:])
    assert np.isfinite(t).all() and np.isfinite(unit_z).all()
    step=radius*t
    original_rows,original_bounds,original_high,original_low=inequalities(matrix,lower,upper)
    assert np.array_equal(high,original_high) and np.array_equal(low,original_low)
    dual_scale=np.r_[radius/row_scale[high],radius/row_scale[low]]
    z=unit_z*dual_scale;y,evidence=metrics(gram,gradient,matrix,lower,upper,step,z,scale)
    original_root=factor/np.sqrt(scale)
    mapped_aux=np.sqrt(radius)*aux;mapped_equality=np.sqrt(radius)*equality_dual
    native=solution.status==clarabel.SolverStatus.Solved
    evidence.update(success=bool(native and certified(evidence,settings)),native_success=bool(native),
        status=str(solution.status),status_value=1 if native else 0,solver_version=clarabel.__version__,
        iterations=int(solution.iterations),native_primal_residual=float(solution.r_prim),
        native_dual_residual=float(solution.r_dual),solve_seconds=float(solution.solve_time),
        external_hessian_regularization=False,linear_constraints=matrix.shape[0],inequality_constraints=len(z),
        primal_solution=step.tolist(),dual_solution=y.tolist(),inequality_dual=z.tolist(),
        auxiliary_solution=mapped_aux.tolist(),equality_dual=mapped_equality.tolist(),
        maximum_lifted_equality_error=float(abs(original_root@step-mapped_aux).max()),
        maximum_auxiliary_stationarity=float(abs(mapped_aux-mapped_equality).max()),
        factor_source='QR_of_declared_weighted_surrogate_no_exact_H_claim',
        unit_transform=dict(radius=radius,row_scales=row_scale.tolist(),objective_divisor=scale*radius,
            unit_primal=t.tolist(),unit_inequality_dual=unit_z.tolist(),unit_auxiliary=aux.tolist(),
            unit_equality_dual=equality_dual.tolist(),stationarity_units_equal_original=True),
        truth_used=False,heldout_used=False)
    if evidence['success']:
        evidence['active_set_polish']=dict(attempted=False)
        return step,evidence
    coarse=evidence
    step,z,refined=polish(gram,gradient,weighted,rhs,original_rows,original_bounds,step,settings)
    y,evidence=metrics(gram,gradient,matrix,lower,upper,step,z,scale)
    passed=bool(refined['success'] and certified(evidence,settings))
    evidence.update(success=passed,native_success=passed,status='SolvedActiveSet' if passed else 'ActiveSetUncertified',
        status_value=1 if passed else 0,external_native_status=coarse['status'],
        termination='independent_original_KKT_certificate',iterations=refined['iterations'],solver_version=clarabel.__version__,
        external_hessian_regularization=False,linear_constraints=matrix.shape[0],inequality_constraints=len(z),
        primal_solution=step.tolist(),dual_solution=y.tolist(),inequality_dual=z.tolist(),coarse_attempt=coarse,
        active_set_polish=dict(attempted=True,**refined),factor_source='original_weighted_surrogate_after_unit_box_coarse',truth_used=False,heldout_used=False)
    return step,evidence


def solve(gram,gradient,weighted,rhs,region,settings):
    return solve_system(gram,gradient,weighted,rhs,*linear_system(region),region.radius,settings)
