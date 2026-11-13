"""Known observation contracts and observed-initialized estimator continuity control."""
import numpy as np
from .overlap_phase import compare,line_from_fit,trajectory
from .peaks import native_peaks
from .rate_coordinates import fit_channel
from .local_chirps import evaluate


def global_quadratic_line(f,q,amplitude,phase,origin,centre):
    dt=centre-origin;z=amplitude*np.exp(1j*(phase+2*np.pi*(f*dt+.5*q*dt*dt)))
    return dict(centre_seconds=centre,frequency_Hz=f+q*dt,chirp_Hz_per_s=q,
        a=float(z.real),b=float(-z.imag),success=True,at_bound=False)


def controls(rate=48000):
    samples=np.arange(rate//2,rate);time=samples/rate
    left=global_quadratic_line(75.2,1.2,.5,.2,.75,.5)
    right=global_quadratic_line(75.2,1.2,.5,.2,.75,1.)
    same,v1,v2=compare(left,right,samples,rate)
    expected=.5*np.exp(1j*(.2+2*np.pi*(75.2*(time-.75)+.6*(time-.75)**2)))
    exact=max(float(abs(v1-expected).max()),float(abs(v2-expected).max()))
    shifted=right.copy();z=complex(right['a'],-right['b'])*np.exp(.37j)
    shifted.update(a=float(z.real),b=float(-z.imag))
    offset,_,_=compare(left,shifted,samples,rate)
    offset_error=max(abs(offset['midpoint_phase_difference_cycles']-.37/(2*np.pi)),
        abs(offset['unit_phasor_rms_distance']-2*np.sin(.37/2)),offset['frequency_difference_max_Hz'])
    silent=left.copy();silent.update(a=0.,b=0.)
    zero,_,_=compare(silent,right,samples,rate)
    # A single global cubic can have disagreeing local quadratic Taylor approximations.
    cubic=[];r=1.2
    for c in (.5,1.):
        u=c-.75;f=75.25+.3*u+.5*r*u*u;q=.3+r*u
        z=.5*np.exp(1j*(.2+2*np.pi*(75.25*u+.15*u*u+r*u**3/6)))
        cubic.append(dict(centre_seconds=c,frequency_Hz=f,chirp_Hz_per_s=q,a=float(z.real),b=float(-z.imag)))
    curved,cv1,cv2=compare(*cubic,samples,rate)
    difference=r*((time-.5)**3-(time-1.)**3)/6
    measured=np.angle(cv2*np.conj(cv1))/(2*np.pi)
    cubic_error=float(abs(measured-difference).max())
    exact_pass=(exact<=1e-10 and same['continuous_phase_max_cycles']<=1e-10
        and same['frequency_difference_max_Hz']<=1e-10 and offset_error<=1e-10
        and not zero['phase_defined'] and zero['wrapped_phase_rms_cycles'] is None and cubic_error<=1e-10)
    assert exact_pass,'Observation contract failed before estimator or recording'
    time=np.arange(3*rate//2)/rate-.75;f=np.array([75.2,112.8,188.,82.3]);q=np.array([1.2,1.8,3.,-.2])
    amp=np.array([.5,.4,.3,.18]);phase=np.array([.2,.5,.8,.1])
    audio=(amp*np.cos(2*np.pi*(time[:,None]*f+.5*time[:,None]**2*q)+phase)).sum(axis=1)
    fitted=[];waves=[];errors=[]
    for start in (0,rate//2):
        part=audio[start:start+rate]
        peaks=native_peaks(np.column_stack((part,part)),rate,[75,113,188,82])
        nominal=peaks['selected_native_bin_Hz'][:,0].astype(float)
        assert np.all(nominal>0)
        parameters,fit=fit_channel(part,rate,nominal);fitted.append(fit)
        wave=evaluate(parameters,nominal,np.arange(rate)/rate-.5)[0];waves.append(wave)
        errors.append(float(np.linalg.norm(wave-part)/np.linalg.norm(part)))
    rows=[]
    for j in range(4):
        a=line_from_fit(fitted[0],[0.,1.],j);b=line_from_fit(fitted[1],[.5,1.5],j)
        row,_,_=compare(a,b,samples,rate);rows.append(row)
    passed=all(x['success'] and not any(x['at_bound']) for x in fitted) and max(errors)<=1e-6
    passed=passed and all(x['wrapped_phase_rms_cycles']<=1e-6 and x['frequency_difference_max_Hz']<=.01 for x in rows)
    return dict(passed=bool(passed),operator_contracts=dict(same_global=same,complex_error=exact,
        retained_offset=offset,offset_error=offset_error,zero_component=zero,
        cubic_local_approximations=curved,cubic_formula_error=cubic_error),
        estimator_control=dict(fits=fitted,waveform_relative_errors=errors,comparisons=rows,
            truth_used_as_fit_initialization=False),
        limits=['Exact translated/cubic coordinates test the observation operator only',
            'Two fitted known model-matched windows do not qualify a common engine phase estimator',
            'Overlap agreement uses shared samples, not independent heldouts'])
