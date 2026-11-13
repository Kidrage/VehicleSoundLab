"""Generic fixed-mask cubic verification fit; never classifies source identity."""
import numpy as np
from scipy.linalg import lstsq
from scipy.optimize import least_squares
from native_phase_patch_v1.basis import projection


def fit(audio,nominal,chirp,plan):
    nominal=np.asarray(nominal,dtype=float)
    chirp=np.asarray(chirp,dtype=float)
    n,m=len(audio),len(nominal)
    if audio.shape!=(12000,2) or chirp.shape!=nominal.shape or not np.isfinite(audio).all():
        raise ValueError('Finite original native stereo/initial rates required')
    if not m or m>plan['maximum_modes']:
        return dict(success=False,reason='empty_or_overflow',lines=[]),{}
    width=np.full(m,plan['frequency_radius_hz'])
    if m>1:
        gaps=np.diff(nominal)
        if min(gaps)<=0:raise ValueError('Distinct ascending current candidate bins required')
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    t=np.arange(n)/48000-.125
    train=np.arange(n)<9000
    native_weight=np.sqrt((.5-.5*np.cos(2*np.pi*np.arange(n)/n))/n)
    weight=native_weight*train
    limit=plan['maximum_chirp_hz_per_second']
    initial_rate=np.clip(chirp,-limit+1e-6,limit-1e-6)
    initial=np.r_[np.zeros(m),initial_rate,initial_rate]
    lower=np.r_[-width,np.full(2*m,-limit)]
    upper=np.r_[width,np.full(2*m,limit)]
    fun,jac,state=projection(audio[:,0],nominal,weight,t,.25)
    tolerance=plan['tolerance']
    solved=least_squares(fun,initial,jac=jac,bounds=(lower,upper),max_nfev=plan['max_evaluations'],
        ftol=tolerance,xtol=tolerance,gtol=tolerance,x_scale='jac')
    current=state(solved.x)
    right,_,rank,_=lstsq(current['weighted'],weight*audio[:,1],lapack_driver='gelsy')
    coefficients=np.column_stack((current['coefficients'],right))
    reconstructed=current['cosine']@coefficients[:m]+current['sine']@coefficients[m:2*m]+coefficients[-1]
    residual=audio-reconstructed
    f=nominal+solved.x[:m]
    qL,qR=solved.x[m:2*m],solved.x[2*m:]
    q=(qL+qR)/2
    curvature=(qR-qL)/.25
    amplitude=np.hypot(coefficients[:m],coefficients[m:2*m])
    power=.5*np.mean(amplitude**2,axis=1)
    floor=max(power)*10**(plan['minimum_line_power_db_relative_to_maximum']/10)
    contact=(abs(solved.x[:m])>=width-1e-7)|(abs(qL)>=limit-1e-7)|(abs(qR)>=limit-1e-7)
    lines=[dict(index=k,nominal_hz=float(nominal[k]),frequency_hz=float(f[k]),
        chirp_hz_per_second=float(q[k]),curvature_hz_per_second2=float(curvature[k]),
        rate_endpoints_hz_per_second=[float(qL[k]),float(qR[k])],amplitude_LR=amplitude[k].tolist(),
        phase_at_midpoint_LR=np.arctan2(-coefficients[m+k],coefficients[k]).tolist(),
        cosine_LR=coefficients[k].tolist(),sine_LR=coefficients[m+k].tolist(),bound_contact=bool(contact[k]),
        relative_power_ok=bool(power[k]>=floor),training_parameter_gate_ok=bool(solved.success and rank==2*m+1 and
            not contact[k] and power[k]>=floor and power[k]>0)) for k in range(m)]
    result=dict(success=bool(solved.success),reason=None,status=int(solved.status),message=solved.message,
        evaluations=int(solved.nfev),rank=int(rank),cost=float(solved.cost),optimality=float(solved.optimality),
        training_cost_LR=np.sum((weight[:,None]*residual)**2,axis=0).tolist(),
        check_cost_LR=np.sum((native_weight[:,None]*(~train)[:,None]*residual)**2,axis=0).tolist(),
        frequency_offset_bounds_hz=width.tolist(),DC_LR=coefficients[-1].tolist(),lines=lines,
        nonlinear_parameter_count=3*m,eliminated_linear_parameter_count=2*m+1,
        training_frames=9000,check_frames=3000,whole_window_candidate_conditioned=True)
    arrays=dict(nominal=nominal,parameters=solved.x,initial=initial,lower=lower,upper=upper,
        coefficients=coefficients,reconstructed=reconstructed,residual=residual,training_mask=train,weight=weight)
    return result,arrays
