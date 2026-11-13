"""Positive affine real amplitudes on independent local chirps; no engine clock."""
import numpy as np
from scipy.optimize import least_squares
from .peaks import native_peaks


def evaluate(parameters,nominal,time):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    angle=2*np.pi*(time[:,None]*f+.5*time[:,None]**2*q)
    cosine=np.cos(angle);sine=np.sin(angle)
    a=parameters[2*m:3*m];b=parameters[3*m:4*m];s=parameters[4*m:5*m]
    carrier=cosine*a+sine*b;gain=1+time[:,None]*s
    phase_derivative=gain*(-sine*a+cosine*b)
    wave=(gain*carrier).sum(axis=1)+parameters[-1]
    jac=np.column_stack((2*np.pi*time[:,None]*phase_derivative,
        np.pi*time[:,None]**2*phase_derivative,gain*cosine,gain*sine,time[:,None]*carrier,np.ones(len(time))))
    return wave,jac


def fit_channel(audio,rate,nominal):
    m=len(nominal);time=np.arange(rate)/rate-.5
    weight=np.sin(np.pi*np.arange(rate)/rate)/np.sqrt(rate)
    initial=np.zeros(5*m+1)
    angle=2*np.pi*time[:,None]*nominal
    linear=np.column_stack((np.cos(angle),np.sin(angle),np.ones(rate)))
    amplitude=np.linalg.lstsq(weight[:,None]*linear,weight*audio,rcond=None)[0]
    initial[2*m:4*m]=amplitude[:-1];initial[-1]=amplitude[-1]
    low=np.r_[np.full(m,-.5),np.full(m,-2.),np.full(2*m,-np.inf),np.full(m,-1.),-np.inf]
    high=-low
    fit=least_squares(lambda value:weight*(evaluate(value,nominal,time)[0]-audio),initial,
        jac=lambda value:weight[:,None]*evaluate(value,nominal,time)[1],bounds=(low,high),
        max_nfev=60,ftol=1e-11,xtol=1e-11,gtol=1e-11)
    at_bound=(abs(fit.x[:m])>=.5-1e-7)|(abs(fit.x[m:2*m])>=2-1e-7)
    slope_bound=abs(fit.x[4*m:5*m])>=1-1e-7
    return fit.x,dict(success=bool(fit.success),status=int(fit.status),message=fit.message,
        function_evaluations=int(fit.nfev),jacobian_evaluations=int(fit.njev),cost=float(fit.cost),
        optimality=float(fit.optimality),at_bound=at_bound.tolist(),slope_at_bound=slope_bound.tolist(),
        initial=initial.tolist(),fitted_parameters=fit.x.tolist(),nominal_Hz=nominal.tolist())


def local_envelopes(audio,rate,nominal):
    observed=native_peaks(audio,rate,nominal)
    eligible=np.zeros_like(observed['supported']);channels=[]
    for ch in range(2):
        used=observed['peak_present'][:,ch]&observed['supported'][:,ch]
        if not used.any():channels.append(dict(success=False,used_lines=[]));continue
        bins=observed['selected_native_bin_Hz'][used,ch].astype(float)
        parameters,fit=fit_channel(audio[:,ch],rate,bins);m=len(bins)
        observed['frequency_Hz'][used,ch]=bins+parameters[:m]
        eligible[used,ch]=fit['success']&~np.array(fit['at_bound'])&~np.array(fit['slope_at_bound'])
        fit['used_lines']=np.flatnonzero(used).tolist();channels.append(fit)
    observed.update(local_envelope_fit=channels,fit_eligible=eligible)
    return observed
