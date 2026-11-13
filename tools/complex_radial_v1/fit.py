"""Original finite trust policy with radial complex robust objective and block Hessian."""
import numpy as np
from aperture_model_v1.forward import real_rows
from joint_trust_v1.constraints import Region
from .loss import cost,hessian_apply,quadratic
from .quadratic import solve


def scales_from_observation(model,outer,controls,target,scale):
    value,phase=model.prediction(outer,controls,True)
    matrix=np.column_stack((phase,model.design(outer)))
    weighted=hessian_apply(value-target,matrix,scale,.5);norms=np.linalg.norm(weighted,axis=0)
    m=model.original
    limits=np.r_[np.full(m.parts,np.pi),np.full(m.phase_count,model.phase_bound),
        np.full(len(m.selected)*m.departure_count,model.departure_bound)]
    theta=np.minimum(1/np.maximum(norms[:len(outer)],1e-30),limits)
    group_norms=norms[len(outer):].reshape(controls.shape).max(axis=1)
    group=np.minimum(1/np.maximum(group_norms,1e-30),np.sqrt(2.))
    return np.r_[theta,np.broadcast_to(group[:,None],controls.shape).ravel()]


def estimate(model,audio,time,plan,variant,settings,initial,progress=None):
    outer,controls=model.unpack(initial);target=real_rows(model.original.aperture.apply(audio[:,0]))
    scale=plan['soft_l1_scale'];scales=scales_from_observation(model,outer,controls,target,scale)
    radius=settings['initial_radius'];initial_cost=cost(model.prediction(outer,controls)-target,scale);history=[]
    for iteration in range(1,settings['maximum_iterations']+1):
        value,phase=model.prediction(outer,controls,True)
        matrix=np.column_stack((phase,model.design(outer)))*scales[None,:];residual=value-target
        before=cost(residual,scale);gram,gradient,weighted,rhs=quadratic(residual,matrix,scale)
        region=Region(model,outer,controls,scales,radius,settings)
        step,qp=solve(gram,gradient,weighted,rhs,region,settings)
        new_outer,new_controls,effective,feasible=region.retract(step)
        predicted=float(-gradient@effective-.5*effective@gram@effective)
        candidate=cost(model.prediction(new_outer,new_controls)-target,scale)
        actual=before-candidate;ratio=actual/predicted if predicted>0 else None
        accepted=bool(qp['success'] and feasible['feasible'] and predicted>0 and actual>0 and ratio>=settings['acceptance_ratio'])
        row=dict(iteration=iteration,radius=radius,before_cost=before,candidate_cost=candidate,
            predicted_reduction=predicted,actual_reduction=actual,ratio=ratio,accepted=accepted,
            scaled_step_maximum=float(abs(effective).max()),qp=qp,feasibility=feasible,
            candidate_outer=new_outer.tolist(),candidate_absolute_amplitudes=new_controls.tolist())
        if accepted:outer,controls=new_outer,new_controls
        history.append(row)
        if progress:progress(row)
        if not accepted or ratio<.25:radius*=.25
        elif ratio>.75 and abs(effective).max()>.8*radius:radius=min(2*radius,settings['maximum_radius'])
        if radius<settings['minimum_radius']:break
    parameters=model.pack(outer,controls);_,phase,envelope=model.original.samples(parameters)
    residual=model.original.prediction(parameters)-target;amplitude=np.hypot(parameters[:model.parts],parameters[model.parts:2*model.parts])
    remaining=sum(amplitude[k]>=plan['rules']['minimum_carrier_amplitude'] for k in range(model.parts) if k not in model.original.selected)
    normalized=float(np.linalg.norm(residual)/np.linalg.norm(target));low,high=model.original.bounds(plan,variant)
    assert max(np.max(low-parameters),np.max(parameters-high))<=1e-9
    return parameters,phase,dict(history=history,iterations=len(history),accepted_steps=sum(r['accepted'] for r in history),
        initial_cost=initial_cost,final_cost=cost(residual,scale),final_radius=radius,normalized_projection_residual=normalized,
        selected_indices=list(model.original.selected),remaining_carriers=int(remaining),minimum_envelope=float(envelope.min()),
        maximum_envelope=float(envelope.max()),minimum_coordinate_step=float(np.diff(time+phase).min()),
        observation_supported=bool(normalized<=variant['maximum_normalized_projection_residual'] and remaining>=variant['minimum_remaining_carriers']
            and envelope.min()>0 and np.diff(time+phase).min()>0),scales=scales.tolist(),solver_success=False,
        convergence='Original finite budget; no nonlinear/global convergence claim',truth_used=False,heldout_used=False)
