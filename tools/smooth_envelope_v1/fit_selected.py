"""Solve a fixed observation-selected amplitude prior with original gates."""
import numpy as np
from scipy.optimize import least_squares
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel


def estimate(audio,time,plan,variant,settings,selected,initial,prior,selection):
    model=MinorityModel(time,plan,variant,selected)
    if prior.shape[1]!=model.parameter_count:
        raise ValueError('Amplitude prior dimension mismatch')
    first=2*model.parts+model.phase_count
    if np.any(prior[:,:first]) or np.any(prior[:,model.base_count:]):
        raise ValueError('Only real amplitude controls may be regularized')
    target=real_rows(model.aperture.apply(audio[:,0]))
    cache={}
    def calculate(parameters):
        if 'parameters' not in cache or not np.array_equal(cache['parameters'],parameters):
            prediction,jacobian=model.prediction(parameters,True)
            cache.update(parameters=parameters.copy(),data=prediction-target,
                residual=np.r_[prediction-target,prior@parameters],jacobian=np.vstack((jacobian,prior)))
        return cache
    fitted=least_squares(lambda x:calculate(x)['residual'].copy(),initial,
        jac=lambda x:calculate(x)['jacobian'].copy(),bounds=model.bounds(plan,variant),
        loss='soft_l1',f_scale=plan['soft_l1_scale'],x_scale='jac',max_nfev=settings['maximum_evaluations'],
        ftol=1e-10,xtol=1e-10,gtol=1e-10)
    _,phase,envelope=model.samples(fitted.x)
    amplitude=np.hypot(fitted.x[:model.parts],fitted.x[model.parts:2*model.parts])
    remaining=sum(amplitude[i]>=plan['rules']['minimum_carrier_amplitude'] for i in range(model.parts) if i not in selected)
    normalized=float(np.linalg.norm(calculate(fitted.x)['data'])/max(np.linalg.norm(target),1e-30))
    supported=bool(normalized<=variant['maximum_normalized_projection_residual'] and
        remaining>=variant['minimum_remaining_carriers'] and envelope.min()>0 and np.min(np.diff(time+phase))>0)
    report=dict(solver_success=bool(fitted.success),message=fitted.message,evaluations=int(fitted.nfev),
        optimality=float(fitted.optimality),parameters=model.parameter_count,
        normalized_projection_residual=normalized,remaining_carriers=int(remaining),observation_supported=supported,
        selected_indices=list(selected),minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        minimum_coordinate_step=float(np.min(np.diff(time+phase))),selection_weight=selection.get('weight'),
        initial_prior_norm=float(np.linalg.norm(prior@initial)),final_prior_norm=float(np.linalg.norm(prior@fitted.x)),
        truth_used=False,heldout_used=False)
    return fitted.x,phase,report
