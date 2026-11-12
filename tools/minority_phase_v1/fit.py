"""Select a bounded minority from observations, then jointly fit the aperture."""
import numpy as np
from scipy.optimize import least_squares
from aperture_model_v1.forward import real_rows
from .model import MinorityModel
from .selection import rank


def estimate(audio,time,plan,variant,baseline):
    selected=[]
    parameters=baseline.copy()
    stages=[]
    model=MinorityModel(time,plan,variant,selected)
    target=real_rows(model.aperture.apply(audio[:,0]))
    while True:
        residual=model.prediction(parameters)-target
        normalized=float(np.linalg.norm(residual)/max(np.linalg.norm(target),1e-30))
        if normalized<=variant['maximum_normalized_projection_residual']:
            break
        if len(selected)>=variant['maximum_departure_partials']:
            break
        ranked=rank(audio,time,parameters,selected,plan,variant)
        stage=dict(before_residual=normalized,ranked=ranked)
        if not ranked or ranked[0]['explained_fraction']<variant['minimum_detection_explained_fraction']:
            stage['status']='insufficient_observed_direction'
            stages.append(stage)
            break
        selected.append(ranked[0]['index'])
        model=MinorityModel(time,plan,variant,selected)
        parameters=np.r_[parameters,np.zeros(model.departure_count)]
        cache={}
        def calculate(x):
            if 'x' not in cache or not np.array_equal(cache['x'],x):
                prediction,jacobian=model.prediction(x,True)
                cache.update(x=x.copy(),residual=prediction-target,jacobian=jacobian)
            return cache
        fitted=least_squares(lambda x:calculate(x)['residual'].copy(),parameters,
            jac=lambda x:calculate(x)['jacobian'].copy(),bounds=model.bounds(plan,variant),
            loss='soft_l1',f_scale=plan['soft_l1_scale'],x_scale='jac',max_nfev=variant['joint_maximum_evaluations'],
            ftol=1e-10,xtol=1e-10,gtol=1e-10)
        parameters=fitted.x
        stage.update(status='fitted',selected_order=ranked[0]['order'],evaluations=int(fitted.nfev),
            solver_success=bool(fitted.success),message=fitted.message,optimality=float(fitted.optimality))
        stages.append(stage)
    _,phase,envelope=model.samples(parameters)
    residual=model.prediction(parameters)-target
    amplitudes=np.hypot(parameters[:model.parts],parameters[model.parts:2*model.parts])
    remaining=sum(amplitudes[index]>=plan['rules']['minimum_carrier_amplitude']
        for index in range(model.parts) if index not in selected)
    normalized=float(np.linalg.norm(residual)/max(np.linalg.norm(target),1e-30))
    supported=bool(normalized<=variant['maximum_normalized_projection_residual'] and
        remaining>=variant['minimum_remaining_carriers'] and envelope.min()>0 and
        np.min(np.diff(time+phase))>0)
    report=dict(stages=stages,selected_indices=selected,selected_orders=[float(model.orders[index]) for index in selected],
        normalized_projection_residual=normalized,remaining_carriers=int(remaining),observation_supported=supported,
        minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        parameters=model.parameter_count,selection_uses_truth=False,selection_uses_heldout=False)
    return phase,parameters,report
