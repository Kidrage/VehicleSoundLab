"""Zero-departure equivalence and independent finite-difference controls."""
import numpy as np
from aperture_model_v1.fit import Model
from .model import MinorityModel


def controls(plan,variant):
    time=np.arange(round(plan['cycles']*plan['samples_per_cycle']))/plan['samples_per_cycle']
    original=Model(time,plan)
    selected=[plan['source_orders'].index(2),plan['source_orders'].index(7)]
    model=MinorityModel(time,plan,variant,selected)
    rng=np.random.default_rng(99071)
    parameters=np.zeros(model.parameter_count)
    parameters[:2*model.parts]=rng.normal(0,.025,2*model.parts)
    parameters[2*model.parts:2*model.parts+model.phase_count]=rng.normal(0,.003,model.phase_count)
    parameters[2*model.parts+model.phase_count:model.base_count]=rng.normal(0,.01,model.parts*model.envelope_count)
    old=original.prediction(parameters[:model.base_count])
    assert np.array_equal(old,model.prediction(parameters))
    parameters[model.base_count:]=rng.normal(0,.03,model.parameter_count-model.base_count)
    _,jacobian=model.prediction(parameters,True)
    rows=[]
    for label,index in [('phase',2*model.parts+37),('departure',model.base_count+41),
                        ('departure_second',model.base_count+model.departure_count+22),('amplitude',model.base_count-12),('mixed',None)]:
        direction=np.zeros(model.parameter_count)
        if index is None:
            direction=rng.normal(size=model.parameter_count)
            direction/=np.linalg.norm(direction)
        else:
            direction[index]=1
        step=1e-6
        measured=(model.prediction(parameters+step*direction)-model.prediction(parameters-step*direction))/(2*step)
        expected=jacobian@direction
        error=float(np.linalg.norm(measured-expected)/max(np.linalg.norm(expected),1e-30))
        rows.append(dict(parameter=label,relative_error=error))
    return dict(zero_departure_exact=True,jacobian=rows,
        passed=all(row['relative_error']<=plan['rules']['maximum_jacobian_relative_error'] for row in rows))
