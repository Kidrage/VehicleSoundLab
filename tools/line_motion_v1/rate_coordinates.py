"""Independent local chirps with an explicit reference fractional-rate bound."""
import numpy as np
from scipy.optimize import least_squares
from .local_chirps import basis,evaluate
from .peaks import native_peaks


def rate_bounds(nominal,reference_Hz,reference_limit_Hz_per_s=2.):
    assert reference_Hz>0 and reference_limit_Hz_per_s>0 and np.all(nominal>0)
    return reference_limit_Hz_per_s*nominal/reference_Hz


def fit_channel(audio,rate,nominal,reference_Hz=None,reference_limit_Hz_per_s=2.):
    m=len(nominal);reference_Hz=float(nominal[0] if reference_Hz is None else reference_Hz)
    limits=rate_bounds(nominal,reference_Hz,reference_limit_Hz_per_s)
    time=np.arange(rate)/rate-.5;weight=np.sin(np.pi*np.arange(rate)/rate)/np.sqrt(rate)
    initial=np.zeros(4*m+1);cosine,sine=basis(initial,nominal,time)
    linear=np.column_stack((cosine,sine,np.ones(rate)))
    initial[2*m:]=np.linalg.lstsq(weight[:,None]*linear,weight*audio,rcond=None)[0]
    low=np.r_[np.full(m,-.5),-limits,np.full(2*m+1,-np.inf)];high=-low
    fit=least_squares(lambda value:weight*(evaluate(value,nominal,time)[0]-audio),initial,
        jac=lambda value:weight[:,None]*evaluate(value,nominal,time)[1],bounds=(low,high),
        max_nfev=60,ftol=1e-11,xtol=1e-11,gtol=1e-11)
    at_bound=(abs(fit.x[:m])>=.5-1e-7)|(abs(fit.x[m:2*m])>=limits-1e-7)
    return fit.x,dict(success=bool(fit.success),status=int(fit.status),message=fit.message,
        function_evaluations=int(fit.nfev),jacobian_evaluations=int(fit.njev),cost=float(fit.cost),
        optimality=float(fit.optimality),at_bound=at_bound.tolist(),initial=initial.tolist(),
        fitted_parameters=fit.x.tolist(),nominal_Hz=nominal.tolist(),reference_Hz=reference_Hz,
        reference_limit_Hz_per_s=reference_limit_Hz_per_s,chirp_limits_Hz_per_s=limits.tolist(),
        policy='Independent local components share fractional-rate B_ref/reference_Hz bound, not a phase clock')


def rate_coordinates(audio,rate,nominal):
    measured=native_peaks(audio,rate,nominal);channels=[];eligible=np.zeros_like(measured['supported'])
    for ch in range(2):
        used=measured['peak_present'][:,ch]&measured['supported'][:,ch]
        if not used.any():channels.append(dict(success=False,used_lines=[]));continue
        bins=measured['selected_native_bin_Hz'][used,ch].astype(float)
        parameters,fit=fit_channel(audio[:,ch],rate,bins);m=len(bins)
        measured['frequency_Hz'][used,ch]=bins+parameters[:m]
        eligible[used,ch]=fit['success']&~np.array(fit['at_bound']);fit['used_lines']=np.flatnonzero(used).tolist();channels.append(fit)
    measured.update(local_rate_fit=channels,fit_eligible=eligible)
    return measured
