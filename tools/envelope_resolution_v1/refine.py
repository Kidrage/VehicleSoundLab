"""Observed geometry and nested real-envelope refinement, without oracle inputs."""
from copy import deepcopy
import numpy as np
from scipy.optimize import least_squares
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel


def geometry(previous):
    plan=deepcopy(previous)
    orders=np.asarray(plan['source_orders'],dtype=float)
    gaps=np.diff(orders)
    if len(orders)<3 or np.any(gaps<=0):
        raise ValueError('At least three distinct ascending measured candidates are required')
    gap=float(gaps.min())
    spacing=min(plan['amplitude_knot_cycles'],1/gap)
    # Round only floating representation of an integer ratio. This avoids
    # nominal5 becoming5.000000000000018 and breaking nested knot locations.
    ratio=plan['amplitude_knot_cycles']/spacing
    if abs(ratio-round(ratio))>1e-10:
        raise ValueError('Current refinement requires nested observed-gap knot intervals')
    spacing=plan['amplitude_knot_cycles']/round(ratio)
    plan['amplitude_knot_cycles']=spacing
    return plan,dict(minimum_measured_order_gap=gap,previous_spacing=previous['amplitude_knot_cycles'],
        spacing=spacing,nested_refinement_ratio=int(round(ratio)),
        rule='min(previous_spacing, reciprocal_minimum_observed_order_gap)',
        truth_used=False,heldout_used=False,strict_bandlimit_claimed=False)


def transfer(time,previous,current,variant,selected,parameters,tolerance):
    old=MinorityModel(time,previous,variant,selected)
    new=MinorityModel(time,current,variant,selected)
    if not np.array_equal(old.phase_basis,new.phase_basis) or not np.array_equal(old.departure_basis,new.departure_basis):
        raise ValueError('Refinement may only change real amplitude resolution')
    out=np.zeros(new.parameter_count)
    start=2*old.parts+old.phase_count
    out[:start]=parameters[:start]
    old_beta=parameters[start:old.base_count].reshape(old.parts,old.envelope_count)
    beta=np.linalg.lstsq(new.envelope_basis,old.envelope_basis@old_beta.T,rcond=None)[0].T
    out[start:new.base_count]=beta.ravel()
    out[new.base_count:]=parameters[old.base_count:]
    lower,upper=new.bounds(current,variant)
    if np.any(out<lower-tolerance) or np.any(out>upper+tolerance):
        raise ValueError('Nested amplitude transfer violates original bounds')
    out=np.clip(out,lower,upper)
    before,phase,envelope=old.samples(parameters)
    after,new_phase,new_envelope=new.samples(out)
    maximum=float(max(abs(before-after).max(),abs(envelope-new_envelope).max(),abs(phase-new_phase).max()))
    if maximum>tolerance:
        raise ValueError('Nested transfer changes the original fitted signal')
    return out,dict(maximum_sample_envelope_phase_difference=maximum,
        original_parameters=old.parameter_count,refined_parameters=new.parameter_count,
        old_envelope_controls=old.envelope_count,new_envelope_controls=new.envelope_count,
        independent_phase_partials=len(selected),bounds_unchanged=True)


def estimate(audio,time,plan,variant,selected,initial,maximum_evaluations):
    model=MinorityModel(time,plan,variant,selected)
    target=real_rows(model.aperture.apply(audio[:,0]))
    cache={}
    def calculate(parameters):
        if 'parameters' not in cache or not np.array_equal(cache['parameters'],parameters):
            prediction,jacobian=model.prediction(parameters,True)
            cache.update(parameters=parameters.copy(),residual=prediction-target,jacobian=jacobian)
        return cache
    fitted=least_squares(lambda x:calculate(x)['residual'].copy(),initial,
        jac=lambda x:calculate(x)['jacobian'].copy(),bounds=model.bounds(plan,variant),
        loss='soft_l1',f_scale=plan['soft_l1_scale'],x_scale='jac',max_nfev=maximum_evaluations,
        ftol=1e-10,xtol=1e-10,gtol=1e-10)
    _,phase,envelope=model.samples(fitted.x)
    residual=calculate(fitted.x)['residual']
    amplitude=np.hypot(fitted.x[:model.parts],fitted.x[model.parts:2*model.parts])
    remaining=sum(amplitude[i]>=plan['rules']['minimum_carrier_amplitude'] for i in range(model.parts) if i not in selected)
    normalized=float(np.linalg.norm(residual)/max(np.linalg.norm(target),1e-30))
    supported=bool(normalized<=variant['maximum_normalized_projection_residual'] and
        remaining>=variant['minimum_remaining_carriers'] and envelope.min()>0 and np.min(np.diff(time+phase))>0)
    report=dict(solver_success=bool(fitted.success),message=fitted.message,evaluations=int(fitted.nfev),
        optimality=float(fitted.optimality),parameters=model.parameter_count,
        normalized_projection_residual=normalized,remaining_carriers=int(remaining),observation_supported=supported,
        selected_indices=list(selected),minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        minimum_coordinate_step=float(np.min(np.diff(time+phase))),truth_used=False,heldout_used=False)
    return fitted.x,phase,report
