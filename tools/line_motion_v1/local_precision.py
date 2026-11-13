"""One bounded linearized correction; preserve physical boxes and actual-cost acceptance."""
import numpy as np
from scipy.optimize import lsq_linear
from .rate_coordinates import fit_channel as original_fit,rate_bounds
from .local_chirps import evaluate
from .peaks import native_peaks


def correct_once(audio,rate,parameters,fit):
    nominal=np.array(fit['nominal_Hz']);m=len(nominal);time=np.arange(rate)/rate-.5
    weight=np.sin(np.pi*np.arange(rate)/rate)/np.sqrt(rate)
    limit=rate_bounds(nominal,fit['reference_Hz'],fit['reference_limit_Hz_per_s'])
    low=np.r_[np.full(m,-.5),-limit,np.full(2*m+1,-np.inf)];high=-low
    signal,jac=evaluate(parameters,nominal,time);residual=weight*(signal-audio);matrix=weight[:,None]*jac
    solution=lsq_linear(matrix,-residual,bounds=(low-parameters,high-parameters),
        method='bvls',tol=1e-11,max_iter=60)
    raw=parameters+solution.x;outside=float(max(0.,np.max(low-raw),np.max(raw-high)))
    candidate=np.minimum(high,np.maximum(low,raw));new_wave,_=evaluate(candidate,nominal,time)
    actual_cost=float(.5*np.dot(weight**2,(new_wave-audio)**2));before_cost=float(.5*np.dot(residual,residual))
    accepted=bool(solution.success and np.isfinite(candidate).all() and outside<=1e-12 and actual_cost<=before_cost)
    chosen=candidate if accepted else parameters;wave,derivative=evaluate(chosen,nominal,time)
    gradient=derivative.T@(weight**2*(wave-audio))
    corrected=dict(fit)
    corrected.update(fitted_parameters=chosen.tolist(),cost=float(.5*np.dot(weight**2,(wave-audio)**2)),
        at_bound=((abs(chosen[:m])>=.5-1e-7)|(abs(chosen[m:2*m])>=limit-1e-7)).tolist(),
        original_optimality=fit['optimality'],optimality=None,raw_gradient_infinity=float(abs(gradient).max()),
        numerical_status='original_fit_plus_one_cost_checked_BVLS_step_NOT_global_convergence')
    record=dict(success=bool(solution.success),status=int(solution.status),message=solution.message,
        iterations=int(solution.nit),linear_cost=float(solution.cost),linear_optimality=float(solution.optimality),
        step=solution.x.tolist(),raw_candidate=raw.tolist(),box_roundoff_violation=outside,
        projected_candidate=candidate.tolist(),before_cost=before_cost,candidate_actual_cost=actual_cost,accepted=accepted)
    return chosen,corrected,record


def fit_channel(audio,rate,nominal):
    parameters,original=original_fit(audio,rate,nominal)
    chosen,fit,record=correct_once(audio,rate,parameters,original)
    fit['original_fit']=original;fit['precision_correction']=record
    return chosen,fit


def precision_coordinates(audio,rate,nominal):
    measured=native_peaks(audio,rate,nominal);channels=[];eligible=np.zeros_like(measured['supported'])
    for ch in range(2):
        used=measured['peak_present'][:,ch]&measured['supported'][:,ch]
        if not used.any():channels.append(dict(success=False,used_lines=[]));continue
        bins=measured['selected_native_bin_Hz'][used,ch].astype(float)
        parameters,fit=fit_channel(audio[:,ch],rate,bins);m=len(bins)
        measured['frequency_Hz'][used,ch]=bins+parameters[:m]
        eligible[used,ch]=fit['success']&~np.array(fit['at_bound']);fit['used_lines']=np.flatnonzero(used).tolist();channels.append(fit)
    measured.update(local_precision_fit=channels,fit_eligible=eligible)
    return measured
