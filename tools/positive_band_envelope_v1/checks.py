"""Full-period bandwidth, positivity and original phase derivative controls."""
import numpy as np
from .basis import basis
from .model import BandModel


def controls(time,plan,variant):
    rng=np.random.default_rng(642091)
    model=BandModel(time,plan,variant,[1])
    period=model.band_evidence['period_coarse_cycles']
    full_time=np.arange(round(period*plan['samples_per_cycle']))/plan['samples_per_cycle']
    full,evidence=basis(full_time,plan['cycles'],model.orders)
    beta=rng.uniform(-plan['amplitude_control_bound'],plan['amplitude_control_bound'],model.envelope_count)
    envelope=1+full@beta
    assert envelope.min()>=1-plan['amplitude_control_bound']-1e-12
    assert envelope.max()<=1+plan['amplitude_control_bound']+1e-12
    spectrum=np.fft.rfft(envelope)
    above=spectrum[evidence['degree']+1:]
    leakage=float(np.sum(abs(above)**2)/np.sum(abs(spectrum)**2))
    assert leakage<1e-24
    parameters=np.zeros(model.parameter_count)
    parameters[:2*model.parts]=rng.normal(0,.025,2*model.parts)
    first=2*model.parts+model.phase_count
    parameters[2*model.parts:first]=rng.normal(0,.003,model.phase_count)
    parameters[first:model.base_count]=rng.uniform(-.1,.1,model.parts*model.envelope_count)
    parameters[model.base_count:]=rng.normal(0,.02,model.departure_count)
    _,jacobian=model.prediction(parameters,True)
    errors=[]
    for label,index in [('amplitude',first+4),('phase',2*model.parts+31),('departure',model.base_count+5)]:
        direction=np.zeros(model.parameter_count)
        direction[index]=1
        step=1e-6
        measured=(model.prediction(parameters+step*direction)-model.prediction(parameters-step*direction))/(2*step)
        expected=jacobian@direction
        error=float(np.linalg.norm(measured-expected)/max(np.linalg.norm(expected),1e-30))
        assert error<plan['rules']['maximum_jacobian_relative_error']
        errors.append(dict(direction=label,relative_error=error))
    return dict(passed=True,literal_band_outside_energy_fraction=leakage,
        minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        jacobian=errors,band=evidence,positivity_from_bounded_partition=True)
