"""Local predictive risk with exact correlated-aperture white-noise traces."""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit
from .covariance import adjoint,covariance_trace


def select(model,initial,target,unit_prior):
    prediction,jacobian=model.prediction(initial,True)
    residual=prediction-target
    scales=1/np.maximum(np.linalg.norm(jacobian,axis=0),1e-30)
    u,s,vt=np.linalg.svd(jacobian*scales,full_matrices=False)
    tolerance=np.finfo(float).eps*max(jacobian.shape)*s[0]
    keep=s>tolerance
    u,s,vt=u[:,keep],s[keep],vt[keep]
    projected=-u.T@residual
    orthogonal=residual+u@projected
    trace_total=covariance_trace(model.aperture)
    source_basis=adjoint(model.aperture,u,len(model.time))
    trace_fitted=float(np.sum(source_basis**2))
    noise_trace=trace_total-trace_fitted
    if noise_trace<=np.finfo(float).eps*trace_total:
        raise ValueError('Observed model leaves no independent residual noise trace')
    variance=float(np.dot(orthogonal,orthogonal)/noise_trace)
    # Whiten by the *Jacobian*, not by a guessed diagonal window covariance.
    # The exact covariance is used in the predictive-risk trace below.
    parameter_map=(scales[:,None]*vt.T)/s
    mapped=unit_prior@parameter_map
    left,penalty_singular,right=np.linalg.svd(mapped,full_matrices=False)
    threshold=np.finfo(float).eps*max(mapped.shape)*max(penalty_singular[0],1e-30)
    active=penalty_singular>threshold
    left,penalty_singular,right=left[:,active],penalty_singular[active],right[active]
    if not len(penalty_singular):
        return np.zeros_like(unit_prior),dict(weight=0.,reason='No observed amplitude roughness direction',truth_used=False,heldout_used=False)
    shift=left.T@(mapped@projected+unit_prior@initial)
    mode_covariance=np.sum((source_basis@right.T)**2,axis=0)
    log_s=np.log(penalty_singular)
    orthogonal_power=float(np.dot(orthogonal,orthogonal))
    def risk(log_weight,details=False):
        shrink=expit(log_weight+2*log_s)
        displacement=shrink*shift/penalty_singular
        data_power=orthogonal_power+float(np.dot(displacement,displacement))
        trace=float(trace_fitted-np.dot(shrink,mode_covariance))
        value=float(data_power+2*variance*trace-variance*trace_total)
        if details:
            return dict(log_weight=float(log_weight),weight=float(np.exp(log_weight)),risk=value,
                predicted_projection_residual_power=data_power,noise_hat_trace=trace)
        return value
    low=float(-2*max(log_s)-np.log(1e8))
    high=float(-2*min(log_s)+np.log(1e8))
    chosen=minimize_scalar(risk,method='bounded',bounds=(low,high),options=dict(xatol=1e-7))
    candidates=[risk(float(chosen.x),True),risk(low,True),risk(high,True)]
    best=min(candidates,key=lambda row:row['risk'])
    weight=best['weight']
    evidence=dict(**best,selector='local_sure_exact_aperture_covariance',
        source_white_noise_variance_proxy=variance,source_white_noise_standard_deviation_proxy=float(np.sqrt(variance)),
        projection_covariance_trace=trace_total,jacobian_noise_trace=trace_fitted,orthogonal_noise_trace=noise_trace,
        jacobian_rank=int(len(s)),prior_rank=int(len(penalty_singular)),scalar_evaluations=int(chosen.nfev),
        search_log_weight_bounds=[low,high],endpoint_selected=best is not candidates[0],
        risk_curve=[risk(float(value),True) for value in np.linspace(low,high,81)],
        local_linear_only=True,active_bounds_accounted=False,source_white_noise_assumed=True,
        real_noise_calibrated=False,truth_used=False,heldout_used=False)
    return np.sqrt(weight)*unit_prior,evidence
