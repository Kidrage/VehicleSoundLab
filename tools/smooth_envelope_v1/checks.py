"""Exact cubic quadrature and amplitude-only prior controls."""
import numpy as np
from scipy.interpolate import BSpline
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from .penalty import build


def controls(time,plan,variant,settings):
    model=MinorityModel(time,plan,variant,[1])
    rng=np.random.default_rng(739174)
    parameters=np.zeros(model.parameter_count)
    parameters[:2*model.parts]=rng.normal(0,.025,2*model.parts)
    first=2*model.parts+model.phase_count
    parameters[first:model.base_count]=rng.normal(0,.03,model.parts*model.envelope_count)
    parameters[2*model.parts:first]=rng.normal(0,.003,model.phase_count)
    parameters[model.base_count:]=rng.normal(0,.02,model.departure_count)
    target=model.prediction(parameters)+rng.normal(0,1e-5,len(model.prediction(parameters)))
    prior,evidence=build(model,parameters,target,plan,settings)
    assert np.all(prior[:,:first]==0) and np.all(prior[:,model.base_count:]==0)
    # Independent dense quadrature of one third derivative checks the exact
    # interval formula, including clamped endpoint basis functions.
    intervals=np.asarray(evidence['quadrature_intervals'])
    knots=np.r_[[0.]*4,intervals[1:-1],[float(plan['cycles'])]*4]
    beta=parameters[first:first+model.envelope_count]
    curve=BSpline(knots,np.r_[0.,beta],3).derivative(3)
    scalar=0.
    for low,high in zip(intervals[:-1],intervals[1:]):
        points=low+(np.arange(127)+.5)*(high-low)/127
        scalar+=float(np.mean(curve(points)**2)*(high-low))
    scale=evidence['projection_residual_scale_proxy']/(evidence['amplitude_prior_standard_deviation']*
        (2*np.pi*evidence['cutoff_cycles_per_coarse_cycle'])**3)
    measured=float(np.sum((prior@parameters)[:len(intervals)-1]**2))
    quadrature_error=abs(measured-scalar*scale**2)/max(scalar*scale**2,1e-30)
    assert quadrature_error<1e-12
    direction=rng.normal(size=model.parameter_count)
    direction/=np.linalg.norm(direction)
    delta=1e-6
    numeric=(prior@(parameters+delta*direction)-prior@(parameters-delta*direction))/(2*delta)
    derivative_error=float(np.linalg.norm(numeric-prior@direction)/max(np.linalg.norm(prior@direction),1e-30))
    assert derivative_error<1e-7
    zero,evidence_zero=build(model,parameters,model.prediction(parameters),plan,settings)
    assert evidence_zero['projection_residual_scale_proxy']==0 and np.all(zero==0)
    return dict(passed=True,exact_quadrature_relative_error=quadrature_error,
        prior_derivative_relative_error=derivative_error,phase_columns_exactly_zero=True,
        zero_residual_prior_exactly_zero=True,observation_evidence=evidence)
