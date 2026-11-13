"""Native independent multichirp adapter with explicit conditional support."""
import numpy as np
from scipy.linalg import lstsq
from scipy.optimize import least_squares
from line_motion_v1.local_chirps import basis,evaluate


def fit(audio,nominal,chirp,plan):
    n=len(audio);rate=plan['sample_rate'];nominal=np.asarray(nominal,dtype=float);chirp=np.asarray(chirp,dtype=float)
    count=len(nominal)
    if audio.shape!=(plan['frames'],2) or not np.isfinite(audio).all() or chirp.shape!=nominal.shape:
        raise ValueError('Expected native finite stereo and matching initial frequencies/chirps')
    if not count or count>plan['maximum_modes']:return dict(success=False,reason='empty_or_overflow',lines=[]),{}
    t=np.arange(n)/rate-n/(2*rate);window=.5-.5*np.cos(2*np.pi*np.arange(n)/n);w=np.sqrt(window/n)
    width=np.full(count,plan['frequency_radius_hz'])
    if count>1:
        gaps=np.diff(nominal)
        if np.any(gaps<=0):raise ValueError('Expected distinct ascending native frequencies')
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    qmax=plan['maximum_chirp_hz_per_second'];initial=np.zeros(4*count+1)
    initial[count:2*count]=np.clip(chirp,-qmax+1e-6,qmax-1e-6)
    cosine,sine=basis(initial,nominal,t);linear=np.column_stack((cosine,sine,np.ones(n)))
    initial[2*count:]=lstsq(w[:,None]*linear,w*audio[:,0],lapack_driver='gelsy')[0]
    lower=np.r_[-width,np.full(count,-qmax),np.full(2*count+1,-np.inf)]
    upper=np.r_[width,np.full(count,qmax),np.full(2*count+1,np.inf)]
    def fun(p):return w*(evaluate(p,nominal,t)[0]-audio[:,0])
    def jac(p):return w[:,None]*evaluate(p,nominal,t)[1]
    tol=plan['tolerance']
    solved=least_squares(fun,initial,jac=jac,bounds=(lower,upper),max_nfev=plan['max_evaluations'],
        ftol=tol,xtol=tol,gtol=tol,x_scale='jac')
    p=solved.x;cosine,sine=basis(p,nominal,t);linear=np.column_stack((cosine,sine,np.ones(n)))
    right,_,rank,_=lstsq(w[:,None]*linear,w*audio[:,1],lapack_driver='gelsy')
    coefficients=np.column_stack((p[2*count:],right));stems=cosine[:,:,None]*coefficients[:count]+sine[:,:,None]*coefficients[count:2*count]
    residual=audio-stems.sum(axis=1)-coefficients[-1];zres=np.fft.rfft(residual*window[:,None],axis=0)
    hz=np.fft.rfftfreq(n,1/rate);f=nominal+p[:count];q=p[count:2*count]
    contact=(abs(p[:count])>=width-1e-7)|(abs(q)>=qmax-1e-7)
    amplitude=np.hypot(coefficients[:count],coefficients[count:2*count]);power=.5*np.mean(amplitude*amplitude,axis=1)
    floor=power.max(initial=0)*10**(plan['minimum_line_power_db_relative_to_maximum']/10)
    lines=[]
    for k in range(count):
        extent=abs(q[k])*n/(2*rate)+plan['support_padding_hz'];mask=(hz>=f[k]-extent)&(hz<=f[k]+extent)
        zline=np.fft.rfft(stems[:,k]*window[:,None],axis=0)
        observed=np.sum(abs((zres+zline)[mask])**2,axis=0);remaining=np.sum(abs(zres[mask])**2,axis=0)
        explained=1-np.divide(remaining,observed,out=np.ones(2),where=observed>0)
        eligible=bool(solved.success and rank==2*count+1 and not contact[k] and power[k]>=floor and power[k]>0 and
                      np.min(explained)>=plan['minimum_local_explained_fraction'])
        lines.append(dict(index=k,nominal_hz=float(nominal[k]),frequency_hz=float(f[k]),chirp_hz_per_second=float(q[k]),
            amplitude_LR=amplitude[k].tolist(),phase_at_midpoint_LR=np.arctan2(-coefficients[count+k],coefficients[k]).tolist(),
            cosine_LR=coefficients[k].tolist(),sine_LR=coefficients[count+k].tolist(),
            bound_contact=bool(contact[k]),relative_power_ok=bool(power[k]>=floor),
            local_explained_fraction_LR=explained.tolist(),eligible=eligible))
    result=dict(success=bool(solved.success),reason=None,status=int(solved.status),message=solved.message,
        evaluations=int(solved.nfev),rank=int(rank),cost=float(solved.cost),optimality=float(solved.optimality),
        weighted_relative_residual_LR=(np.linalg.norm(w[:,None]*residual,axis=0)/np.maximum(np.linalg.norm(w[:,None]*audio,axis=0),1e-300)).tolist(),
        frequency_offset_bounds_hz=width.tolist(),DC_LR=coefficients[-1].tolist(),lines=lines)
    return result,dict(nominal=nominal,parameters=p,initial=initial,right_coefficients=right,lower=lower,upper=upper,
                       reconstructed=stems.sum(axis=1)+coefficients[-1],residual=residual)
