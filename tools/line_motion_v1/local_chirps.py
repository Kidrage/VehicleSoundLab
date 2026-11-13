"""Observed local multichirp fit; independent phases and no common engine clock."""
import numpy as np
from scipy.optimize import least_squares
from .peaks import native_peaks


def basis(parameters,nominal,time):
    count=len(nominal)
    frequency=nominal+parameters[:count]
    rate=parameters[count:2*count]
    angle=2*np.pi*(time[:,None]*frequency+.5*time[:,None]**2*rate)
    return np.cos(angle),np.sin(angle)


def evaluate(parameters,nominal,time):
    count=len(nominal);cosine,sine=basis(parameters,nominal,time)
    a=parameters[2*count:3*count];b=parameters[3*count:4*count]
    signal=cosine@a+sine@b+parameters[-1]
    derivative=-sine*a+cosine*b
    jacobian=np.column_stack((derivative*(2*np.pi*time[:,None]),
        derivative*(np.pi*time[:,None]**2),cosine,sine,np.ones(len(time))))
    return signal,jacobian


def fit_channel(audio,rate,nominal):
    count=len(nominal)
    time=np.arange(rate)/rate-.5
    weight=np.sin(np.pi*np.arange(rate)/rate)/np.sqrt(rate)
    initial=np.zeros(4*count+1)
    cosine,sine=basis(initial,nominal,time)
    linear=np.column_stack((cosine,sine,np.ones(rate)))
    initial[2*count:]=np.linalg.lstsq(weight[:,None]*linear,weight*audio,rcond=None)[0]
    def fun(value):return weight*(evaluate(value,nominal,time)[0]-audio)
    def jac(value):return weight[:,None]*evaluate(value,nominal,time)[1]
    low=np.r_[np.full(count,-.5),np.full(count,-2.),np.full(2*count+1,-np.inf)]
    high=np.r_[np.full(count,.5),np.full(count,2.),np.full(2*count+1,np.inf)]
    fit=least_squares(fun,initial,jac=jac,bounds=(low,high),max_nfev=60,
        ftol=1e-11,xtol=1e-11,gtol=1e-11)
    at_bound=(abs(fit.x[:count])>=.5-1e-7)|(abs(fit.x[count:2*count])>=2-1e-7)
    return fit.x,dict(success=bool(fit.success),status=int(fit.status),message=fit.message,
        function_evaluations=int(fit.nfev),jacobian_evaluations=int(fit.njev),cost=float(fit.cost),
        optimality=float(fit.optimality),at_bound=at_bound.tolist(),initial=initial.tolist(),
        fitted_parameters=fit.x.tolist(),nominal_Hz=nominal.tolist())


def local_chirps(audio,rate,nominal):
    observed=native_peaks(audio,rate,nominal)
    observed['pre_fit_frequency_Hz']=observed['frequency_Hz'].copy()
    eligible=np.zeros_like(observed['supported'])
    chirp=np.full_like(observed['frequency_Hz'],np.nan)
    channels=[]
    for channel in range(2):
        used=observed['peak_present'][:,channel]&observed['supported'][:,channel]
        if not used.any():
            channels.append(dict(success=False,status=0,message='No supported peak',used_lines=[]));continue
        selected=observed['selected_native_bin_Hz'][used,channel].astype(float)
        parameters,details=fit_channel(audio[:,channel],rate,selected)
        count=len(selected)
        observed['frequency_Hz'][used,channel]=selected+parameters[:count]
        chirp[used,channel]=parameters[count:2*count]
        eligible[used,channel]=details['success']&~np.array(details['at_bound'])
        details['used_lines']=np.flatnonzero(used).tolist();channels.append(details)
    observed.update(fit_eligible=eligible,chirp_Hz_per_second=chirp,local_chirp_fit=channels)
    return observed
