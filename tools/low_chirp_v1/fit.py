"""Independent local chirps, reusing the existing native waveform and Jacobian."""
import numpy as np
from scipy import signal
from scipy.optimize import least_squares
from line_motion_v1.local_chirps import basis, evaluate


def inventory(audio, rate, plan):
    n=len(audio);w=signal.windows.hann(n,sym=False)
    power=abs(np.fft.rfft(w*audio[:,0]))**2
    hz=np.fft.rfftfreq(n,1/rate);lo,hi=plan['frequency_band_hz']
    ix=signal.find_peaks(10*np.log10(power+1e-30),prominence=plan['prominence_db'])[0]
    ix=ix[(hz[ix]>=lo)&(hz[ix]<hi)]
    if len(ix):ix=ix[power[ix]>=power[ix].max()*10**(plan['relative_floor_db']/10)]
    return hz[ix],dict(native_bins=ix.tolist(),native_frequency_hz=hz[ix].tolist(),
        native_power=power[ix].tolist(),overflow=len(ix)>plan['maximum_candidates'])


def fit(audio, rate, plan):
    n=len(audio);assert n==plan['frames'] and rate==plan['sample_rate'] and audio.shape==(n,2)
    nominal,observed=inventory(audio,rate,plan);count=len(nominal)
    result=dict(inventory=observed,lines=[],success=False,source_frames=n)
    if not count or observed['overflow']:
        result['reason']='candidate_overflow' if observed['overflow'] else 'no_candidates'
        return result,dict(parameters=np.empty(0),initial=np.empty(0),right_coefficients=np.empty(0))
    # Same midpoint convention as the original native one-second model.
    t=np.arange(n)/rate-n/(2*rate)
    w=np.sqrt(signal.windows.hann(n,sym=False)/n)
    initial=np.zeros(4*count+1)
    cosine,sine=basis(initial,nominal,t)
    linear=np.column_stack((cosine,sine,np.ones(n)))
    initial[2*count:]=np.linalg.lstsq(w[:,None]*linear,w*audio[:,0],rcond=None)[0]
    width=np.full(count,plan['frequency_half_bin_fraction']*rate/(2*n))
    if count>1:
        gaps=np.diff(nominal)
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    qmax=plan['maximum_chirp_hz_per_second']
    lower=np.r_[-width,np.full(count,-qmax),np.full(2*count+1,-np.inf)]
    upper=np.r_[width,np.full(count,qmax),np.full(2*count+1,np.inf)]
    def fun(p):return w*(evaluate(p,nominal,t)[0]-audio[:,0])
    def jac(p):return w[:,None]*evaluate(p,nominal,t)[1]
    tol=plan['tolerance']
    solved=least_squares(fun,initial,jac=jac,bounds=(lower,upper),max_nfev=plan['max_evaluations'],
        ftol=tol,xtol=tol,gtol=tol)
    p=solved.x;cosine,sine=basis(p,nominal,t)
    linear=np.column_stack((cosine,sine,np.ones(n)))
    right=np.linalg.lstsq(w[:,None]*linear,w*audio[:,1],rcond=None)[0]
    left=p[2*count:];coefficients=np.column_stack((left,right))
    stems=cosine[:,:,None]*coefficients[:count]+sine[:,:,None]*coefficients[count:2*count]
    residual=audio-stems.sum(axis=1)-coefficients[-1]
    f=nominal+p[:count];q=p[count:2*count]
    contact=(abs(p[:count])>=width-1e-7)|(abs(q)>=qmax-1e-7)
    window=signal.windows.hann(n,sym=False)
    zres=np.fft.rfft(residual*window[:,None],axis=0)
    frequency=np.fft.rfftfreq(n,1/rate)
    for i in range(count):
        extent=abs(q[i])*n/(2*rate)+plan['support_padding_hz']
        mask=(frequency>=f[i]-extent)&(frequency<=f[i]+extent)
        zline=np.fft.rfft(stems[:,i]*window[:,None],axis=0)
        observed_power=np.sum(abs((zres+zline)[mask])**2,axis=0)
        residual_power=np.sum(abs(zres[mask])**2,axis=0)
        explained=1-np.divide(residual_power,observed_power,out=np.ones(2),where=observed_power>0)
        eligible=bool(solved.success and not contact[i] and np.min(explained)>=plan['minimum_local_explained_fraction'])
        result['lines'].append(dict(index=i,nominal_hz=float(nominal[i]),frequency_hz=float(f[i]),
            chirp_hz_per_second=float(q[i]),bound_contact=bool(contact[i]),
            local_explained_fraction_LR=explained.tolist(),eligible=eligible,
            cosine_LR=coefficients[i].tolist(),sine_LR=coefficients[count+i].tolist()))
    result.update(success=bool(solved.success),status=int(solved.status),message=solved.message,
        evaluations=int(solved.nfev),cost=float(solved.cost),optimality=float(solved.optimality),
        weighted_relative_residual_LR=(np.linalg.norm(w[:,None]*residual,axis=0)/np.maximum(
            np.linalg.norm(w[:,None]*audio,axis=0),1e-300)).tolist(),
        frequency_offset_bounds_hz=width.tolist(),DC_LR=coefficients[-1].tolist(),reason=None)
    return result,dict(parameters=p,initial=initial,right_coefficients=right,lower=lower,upper=upper,
        reconstructed=stems.sum(axis=1)+coefficients[-1],residual=residual)
