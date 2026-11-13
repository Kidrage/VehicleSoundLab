"""Scalar residual geometry with separately reported nearzero-gradient bound."""
import math
import numpy as np
from complex_radial_v1.audit import relative
from radial_majorizer_v1.geometry import quadratic, weights


def geometry(residual, matrix, scale):
    n=len(residual)//2
    v=np.array([1/math.sqrt(1+(float(residual[k])**2+float(residual[k+n])**2)/scale**2) for k in range(n)])
    diagonal=np.r_[v,v]; independent=matrix*np.sqrt(diagonal)[:,None]
    gram,g,weighted,rhs=quadratic(residual,matrix,scale)
    errors=dict(weighted=relative(independent,weighted),gram=relative(independent.T@independent,gram),
        gradient=relative(matrix.T@(diagonal*residual),g),rhs=relative(-np.sqrt(diagonal)*residual,rhs))
    assert max(errors.values()) <= 1e-12
    original_relative=relative(weighted.T@rhs,-g)
    # The old1e-12 relative gate is recorded, never silently relaxed.
    original_passed=bool(original_relative <= 1e-12)
    actual_v=weights(residual,scale); psi=np.r_[actual_v,actual_v]*residual
    assert np.array_equal(matrix.T@psi,g)
    a=weighted*rhs[:,None]; b=matrix*psi[:,None]
    count=len(residual); eps=np.finfo(float).eps
    gamma=(count+4)*eps/(1-(count+4)*eps)
    bound=(np.sum(abs(a+b),axis=0)+gamma*np.sum(abs(a)+abs(b),axis=0))/(1-gamma)
    error=abs(weighted.T@rhs+g)
    assert np.all(error <= bound)
    forward=dict(original_relative=original_relative,original_gate1e12_passed=original_passed,
        absolute_norm=float(np.linalg.norm(error)),forward_bound_norm=float(np.linalg.norm(bound)),
        component_bound_passed=True,gamma=float(gamma),old_tolerance_changed=False)
    return gram,g,weighted,errors,v,forward
