"""Original QR-lifted constrained QP adapter for an exact block-Hessian factor."""
import numpy as np
from joint_trust_v1.osqp_backend import linear_system
from interior_qp_v1.square_root import solve_factorized
from interior_qp_v1.backend import inequalities
from interior_qp_v1.active_set import polish


def solve(gram,gradient,weighted,rhs,region,settings):
    assert np.linalg.norm(weighted.T@weighted-gram)<=1e-12*max(1.,np.linalg.norm(gram))
    assert np.linalg.norm(weighted.T@rhs+gradient)<=1e-12*max(1.,np.linalg.norm(gradient))
    ranged,lower,upper=linear_system(region)
    step,coarse=solve_factorized(gram,gradient,ranged,lower,upper,settings,np.linalg.qr(weighted,mode='r'))
    if coarse['success']:
        coarse['active_set_polish']=dict(attempted=False)
        return step,coarse
    rows,bounds,high,low=inequalities(ranged,lower,upper)
    step,z,evidence=polish(gram,gradient,weighted,rhs,rows,bounds,step,settings)
    y=np.zeros(ranged.shape[0]);y[high]+=z[:len(high)];y[low]-=z[len(high):]
    scale=coarse['objective_scale'];normal=(gram+gram.T)/(2*scale);value=ranged@step
    primal=float(max(0.,np.max(lower-value),np.max(value-upper)))
    dual=float(abs(normal@step+gradient/scale+ranged.T@y).max())
    sign=float(max(0.,-z.min()));comp=float(abs(z*(bounds-rows@step)).max())
    success=bool(evidence['success'] and primal<=settings['maximum_primal_violation']
        and dual<=settings['maximum_normalized_stationarity'] and sign<=settings['maximum_primal_violation']
        and comp<=settings['maximum_complementarity'])
    return step,dict(success=success,status='SolvedActiveSet' if success else 'ActiveSetUncertified',
        status_value=1 if success else 0,native_success=success,external_native_status=coarse['status'],
        termination='independent_original_KKT_certificate',iterations=evidence['iterations'],solver_version=coarse['solver_version'],
        normalized_dual_stationarity=dual,constraint_violation=primal,inequality_dual_sign_violation=sign,
        maximum_complementarity=comp,normalized_duality_gap=float(z@(bounds-rows@step)),
        original_objective_dual_stationarity=dual*scale,objective_scale=scale,
        objective=float(.5*step@gram@step+gradient@step),external_hessian_regularization=False,
        linear_constraints=ranged.shape[0],inequality_constraints=len(bounds),primal_solution=step.tolist(),
        dual_solution=y.tolist(),inequality_dual=z.tolist(),coarse_attempt=coarse,
        active_set_polish=dict(attempted=True,**evidence),factor_source='exact_complex_block_Hessian_weighted_Jacobian',
        truth_used=False,heldout_used=False)
