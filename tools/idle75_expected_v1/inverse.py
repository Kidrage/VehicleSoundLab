"""Fixed bounded expected-moment inverse; never fits a random take clock."""
import numpy as np
from scipy.optimize import least_squares


def fit(expected,target):
    target=np.asarray(target);scale=target[0];trace=[]
    if scale<=0:raise ValueError('Positive target variance required')
    def fun(p):
        value,jac,minimum=expected(p);e=(value-target)/scale
        trace.append(dict(parameters=np.asarray(p).tolist(),moments=value.tolist(),jacobian=jac.tolist(),
            squared_error=float(e@e),minimum_centered_window_covariance_eigenvalue=minimum))
        return e
    result=least_squares(fun,[1.,1.],jac=lambda p:expected(p)[1]/scale,bounds=([.5,.25],[4.,3.]),
        max_nfev=40,xtol=1e-10,ftol=1e-10,gtol=1e-10)
    value,jac,minimum=expected(result.x);singular=np.linalg.svd(jac/scale,compute_uv=False)
    condition=float(singular[0]/singular[-1]);rank=int(np.linalg.matrix_rank(jac))
    return dict(available=bool(result.success and not np.any(result.active_mask) and rank==2 and condition<=1e4),
        parameters=result.x.tolist(),success=bool(result.success),status=result.status,nfev=result.nfev,njev=result.njev,
        active_mask=result.active_mask.tolist(),rank=rank,condition=condition,singular_values=singular.tolist(),
        target=target.tolist(),prediction=value.tolist(),scaled_squared_error=float(np.sum(((value-target)/scale)**2)),
        minimum_centered_window_covariance_eigenvalue=minimum,trace=trace)
