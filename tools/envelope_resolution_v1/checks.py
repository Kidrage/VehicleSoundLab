"""Nested representation and derivative controls independent of fixture truth."""
import numpy as np
from minority_phase_v1.model import MinorityModel
from .refine import geometry,transfer


def controls(time,previous,variant,tolerance):
    current,evidence=geometry(previous)
    old=MinorityModel(time,previous,variant,[1])
    rng=np.random.default_rng(382976)
    parameters=np.zeros(old.parameter_count)
    parameters[:2*old.parts]=rng.normal(0,.025,2*old.parts)
    begin=2*old.parts
    parameters[begin:begin+old.phase_count]=rng.normal(0,.003,old.phase_count)
    begin+=old.phase_count
    parameters[begin:old.base_count]=rng.uniform(-.2,.2,old.parts*old.envelope_count)
    parameters[old.base_count:]=rng.normal(0,.03,old.departure_count)
    initial,matched=transfer(time,previous,current,variant,[1],parameters,tolerance)
    model=MinorityModel(time,current,variant,[1])
    _,jacobian=model.prediction(initial,True)
    derivatives=[]
    for name,index in [('envelope',2*model.parts+model.phase_count+3),('departure',model.base_count+5),('mixed',None)]:
        direction=np.zeros(model.parameter_count)
        if index is None:
            direction=rng.normal(size=model.parameter_count)
            direction/=np.linalg.norm(direction)
        else:
            direction[index]=1
        delta=1e-6
        measured=(model.prediction(initial+delta*direction)-model.prediction(initial-delta*direction))/(2*delta)
        expected=jacobian@direction
        error=float(np.linalg.norm(measured-expected)/max(np.linalg.norm(expected),1e-30))
        derivatives.append(dict(name=name,relative_error=error))
    rejected=[]
    for orders in ([1,2],[1,1,2],[2,1,3]):
        try:
            geometry({**previous,'source_orders':orders})
        except ValueError:
            rejected.append(orders)
        else:
            raise AssertionError('Invalid observed topology accepted')
    assert len(rejected)==3
    assert all(row['relative_error']<=previous['rules']['maximum_jacobian_relative_error'] for row in derivatives)
    return dict(passed=True,geometry=evidence,nested_transfer=matched,jacobian=derivatives,invalid_topologies_rejected=rejected)
