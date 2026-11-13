"""Independent cubic-phase stereo patches; no driver, shared clock or source labels."""
import numpy as np
from scipy.linalg import lstsq
from scipy.optimize import least_squares
from .basis import projection,frequency_extent


def fit(audio,nominal,chirp,plan):
    nominal=np.asarray(nominal,dtype=float)
    chirp=np.asarray(chirp,dtype=float)
    n,m=len(audio),len(nominal)
    if audio.shape!=(plan['frames'],2) or chirp.shape!=nominal.shape or not np.isfinite(audio).all():
        raise ValueError('Finite native stereo and observed initial rates required')
    if not m or m>plan['maximum_modes']:
        return dict(success=False,reason='empty_or_overflow',lines=[]),{}
    width=np.full(m,plan['frequency_radius_hz'])
    if m>1:
        gaps=np.diff(nominal)
        if min(gaps)<=0:raise ValueError('Distinct ascending native frequencies required')
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    duration=n/plan['sample_rate']
    t=np.arange(n)/plan['sample_rate']-duration/2
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    w=np.sqrt(window/n)
    limit=plan['maximum_chirp_hz_per_second']
    initial_rate=np.clip(chirp,-limit+1e-6,limit-1e-6)
    initial=np.r_[np.zeros(m),initial_rate,initial_rate]
    lower=np.r_[-width,np.full(2*m,-limit)]
    upper=np.r_[width,np.full(2*m,limit)]
    fun,jac,state=projection(audio[:,0],nominal,w,t,duration)
    tol=plan['tolerance']
    solved=least_squares(fun,initial,jac=jac,bounds=(lower,upper),max_nfev=plan['max_evaluations'],
        ftol=tol,xtol=tol,gtol=tol,x_scale='jac')
    s=state(solved.x)
    right,_,rank,_=lstsq(s['weighted'],w*audio[:,1],lapack_driver='gelsy')
    co=np.column_stack((s['coefficients'],right))
    stems=s['cosine'][:,:,None]*co[:m]+s['sine'][:,:,None]*co[m:2*m]
    residual=audio-stems.sum(axis=1)-co[-1]
    f=nominal+solved.x[:m]
    qL,qR=solved.x[m:2*m],solved.x[2*m:]
    q=(qL+qR)/2
    a=(qR-qL)/duration
    amp=np.hypot(co[:m],co[m:2*m])
    power=.5*np.mean(amp**2,axis=1)
    floor=power.max()*10**(plan['minimum_line_power_db_relative_to_maximum']/10)
    contact=(abs(solved.x[:m])>=width-1e-7)|(abs(qL)>=limit-1e-7)|(abs(qR)>=limit-1e-7)
    zr=np.fft.rfft(residual*window[:,None],axis=0)
    hz=np.fft.rfftfreq(n,1/plan['sample_rate'])
    lines=[]
    for k in range(m):
        extent=frequency_extent(q[k],a[k],duration)+plan['support_padding_hz']
        mask=(hz>=f[k]-extent)&(hz<=f[k]+extent)
        zl=np.fft.rfft(stems[:,k]*window[:,None],axis=0)
        before=np.sum(abs((zr+zl)[mask])**2,axis=0)
        after=np.sum(abs(zr[mask])**2,axis=0)
        support=1-np.divide(after,before,out=np.ones(2),where=before>0)
        eligible=bool(solved.success and rank==2*m+1 and not contact[k] and power[k]>=floor and power[k]>0 and min(support)>=plan['minimum_local_explained_fraction'])
        lines.append(dict(index=k,nominal_hz=float(nominal[k]),frequency_hz=float(f[k]),
            chirp_hz_per_second=float(q[k]),curvature_hz_per_second2=float(a[k]),
            rate_endpoints_hz_per_second=[float(qL[k]),float(qR[k])],
            amplitude_LR=amp[k].tolist(),phase_at_midpoint_LR=np.arctan2(-co[m+k],co[k]).tolist(),
            cosine_LR=co[k].tolist(),sine_LR=co[m+k].tolist(),bound_contact=bool(contact[k]),
            relative_power_ok=bool(power[k]>=floor),support_extent_hz=float(extent),
            local_explained_fraction_LR=support.tolist(),eligible=eligible))
    result=dict(success=bool(solved.success),reason=None,status=int(solved.status),message=solved.message,
        evaluations=int(solved.nfev),rank=int(rank),cost=float(solved.cost),optimality=float(solved.optimality),
        weighted_relative_residual_LR=(np.linalg.norm(w[:,None]*residual,axis=0)/np.maximum(np.linalg.norm(w[:,None]*audio,axis=0),1e-300)).tolist(),
        frequency_offset_bounds_hz=width.tolist(),DC_LR=co[-1].tolist(),lines=lines,
        nonlinear_parameter_count=3*m,eliminated_linear_parameter_count=2*m+1,
        representation='Cubic phase; both aperture-edge rates remain within original box')
    arrays=dict(nominal=nominal,parameters=solved.x,initial=initial,lower=lower,upper=upper,
        coefficients=co,reconstructed=stems.sum(axis=1)+co[-1],residual=residual)
    return result,arrays
