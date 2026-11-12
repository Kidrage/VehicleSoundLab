"""Bounded observed initialization and fit for positive finite-band amplitudes."""
import numpy as np
from scipy.optimize import least_squares,lsq_linear
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from .model import BandModel


def initialize(time,plan,variant,selected,previous):
    old=MinorityModel(time,plan,variant,selected)
    new=BandModel(time,plan,variant,selected)
    out=np.zeros(new.parameter_count)
    first=2*new.parts+new.phase_count
    out[:first]=previous[:first]
    out[new.base_count:]=previous[old.base_count:]
    envelope=old.samples(previous)[2]
    bounds=plan['amplitude_control_bound']
    for part in range(new.parts):
        fitted=lsq_linear(new.envelope_basis,envelope[:,part]-1,bounds=(-bounds,bounds),tol=1e-12)
        start=first+part*new.envelope_count
        out[start:start+new.envelope_count]=fitted.x
    _,phase,estimated=new.samples(out)
    return out,dict(envelope_initial_approximation_maximum_error=float(abs(estimated-envelope).max()),
        envelope_initial_approximation_rms=float(np.sqrt(np.mean((estimated-envelope)**2))),
        previous_parameters=old.parameter_count,new_parameters=new.parameter_count,
        original_phase_exact=bool(np.array_equal(phase,old.samples(previous)[1])),
        oracle_used=False,band=new.band_evidence)


def estimate(audio,time,plan,variant,settings,selected,initial):
    model=BandModel(time,plan,variant,selected)
    target=real_rows(model.aperture.apply(audio[:,0]))
    cache={}
    def calculate(parameters):
        if 'parameters' not in cache or not np.array_equal(cache['parameters'],parameters):
            value,jacobian=model.prediction(parameters,True)
            cache.update(parameters=parameters.copy(),residual=value-target,jacobian=jacobian)
        return cache
    fitted=least_squares(lambda x:calculate(x)['residual'].copy(),initial,
        jac=lambda x:calculate(x)['jacobian'].copy(),bounds=model.bounds(plan,variant),
        loss='soft_l1',f_scale=plan['soft_l1_scale'],x_scale='jac',max_nfev=settings['maximum_evaluations'],
        ftol=1e-10,xtol=1e-10,gtol=1e-10)
    _,phase,envelope=model.samples(fitted.x)
    amplitude=np.hypot(fitted.x[:model.parts],fitted.x[model.parts:2*model.parts])
    remaining=sum(amplitude[i]>=plan['rules']['minimum_carrier_amplitude'] for i in range(model.parts) if i not in selected)
    normalized=float(np.linalg.norm(calculate(fitted.x)['residual'])/max(np.linalg.norm(target),1e-30))
    supported=bool(normalized<=variant['maximum_normalized_projection_residual'] and
        remaining>=variant['minimum_remaining_carriers'] and envelope.min()>0 and np.min(np.diff(time+phase))>0)
    return fitted.x,phase,dict(solver_success=bool(fitted.success),message=fitted.message,evaluations=int(fitted.nfev),
        optimality=float(fitted.optimality),parameters=model.parameter_count,
        normalized_projection_residual=normalized,remaining_carriers=int(remaining),observation_supported=supported,
        selected_indices=list(selected),minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        minimum_coordinate_step=float(np.min(np.diff(time+phase))),band=model.band_evidence,truth_used=False,heldout_used=False)
