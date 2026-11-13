"""Replay unchanged frequency/recovery gates and retain the exact failed overlap fixture."""
import numpy as np
from .peak_controls import peak_controls
from .chirp_limit_controls import fixtures
from .peaks import native_peaks
from .local_chirps import evaluate
from .local_precision import fit_channel,precision_coordinates
from .overlap_phase_controls import controls as overlap_controls
from .overlap_phase import compare,line_from_fit


def controls(rate=48000):
    prior=peak_controls(observer=precision_coordinates);recovery=[];t=np.arange(rate)/rate-.5
    for case in fixtures(rate):
        measured=native_peaks(np.column_stack((case['audio'],case['audio'])),rate,case['labels'])
        nominal=measured['selected_native_bin_Hz'][:,0].astype(float)
        p,fit=fit_channel(case['audio'],rate,nominal);m=len(nominal)
        f=float(abs(nominal+p[:m]-case['frequency']).max());q=float(abs(p[m:2*m]-case['chirp']).max())
        error=float(np.linalg.norm(evaluate(p,nominal,t)[0]-case['audio'])/np.linalg.norm(case['audio']))
        recovery.append(dict(id=case['id'],fit=fit,frequency_error_Hz=f,chirp_error_Hz_per_s=q,waveform_relative_error=error,
            passed=bool(fit['success'] and not any(fit['at_bound']) and f<=.01 and q<=.01 and error<=1e-6)))
    # Preserve and replay the original failure, rather than moving the fixture off its endpoint.
    original=overlap_controls(rate)
    time=np.arange(3*rate//2)/rate-.75;f=np.array([75.2,112.8,188.,82.3]);q=np.array([1.2,1.8,3.,-.2])
    amp=np.array([.5,.4,.3,.18]);phase=np.array([.2,.5,.8,.1])
    audio=(amp*np.cos(2*np.pi*(time[:,None]*f+.5*time[:,None]**2*q)+phase)).sum(axis=1)
    fits=[];errors=[];expected_flags=[];diagnosis=[]
    for i,start in enumerate((0,rate//2)):
        part=audio[start:start+rate];nominal=np.array(original['estimator_control']['fits'][i]['nominal_Hz'])
        parameters,fit=fit_channel(part,rate,nominal);m=len(nominal);fits.append(fit)
        assert fit['original_fit']==original['estimator_control']['fits'][i]
        errors.append(float(np.linalg.norm(evaluate(parameters,nominal,t)[0]-part)/np.linalg.norm(part)))
        truth=f+q*((start+rate/2)/rate-.75)
        flags=(abs(truth-nominal)>=.5-1e-7)|(abs(q)>=np.array(fit['chirp_limits_Hz_per_s'])-1e-7)
        expected_flags.append(flags.tolist())
        old=fit['original_fit'];old_p=np.array(old['fitted_parameters']);wave,jac=evaluate(old_p,nominal,t)
        weight=np.sin(np.pi*np.arange(rate)/rate)/np.sqrt(rate);g=jac.T@(weight**2*(wave-part))
        low=np.r_[np.full(m,-.5),-np.array(fit['chirp_limits_Hz_per_s']),np.full(2*m+1,-np.inf)];high=-low
        distance=np.where(g<0,high-old_p,old_p-low);distance=np.where(np.isfinite(distance),distance,1.)
        diagnosis.append(dict(raw_gradient_infinity=float(abs(g).max()),distance_scaled_optimality=float(abs(g*distance).max()),
            original_optimality=old['optimality'],expected_true_frequency_Hz=truth.tolist(),expected_bound_flags=flags.tolist()))
    comparisons=[];samples=np.arange(rate//2,rate)
    for j in range(4):
        one=line_from_fit(fits[0],[0,1],j);two=line_from_fit(fits[1],[.5,1.5],j)
        row,_,_=compare(one,two,samples,rate);comparisons.append(row)
    passed=prior['passed'] and all(row['passed'] for row in recovery) and not original['passed']
    passed=passed and max(errors)<=1e-6 and all(fit['success'] and fit['at_bound']==flags for fit,flags in zip(fits,expected_flags))
    passed=passed and all(x['wrapped_phase_rms_cycles']<=1e-6 and x['frequency_difference_max_Hz']<=.01 for x in comparisons)
    return dict(passed=bool(passed),prior_controls=prior,recovery_cases=recovery,original_overlap_control=original,
        precision_overlap=dict(fits=fits,waveform_relative_errors=errors,comparisons=comparisons,diagnosis=diagnosis,
            expected_inclusive_endpoint_flags=expected_flags,truth_used_as_fit_initialization=False),
        limits=['Original failure retained/replayed; only invalid no-bound expectation corrected for true inclusive endpoint',
            'Original phase/waveform thresholds remain; one BVLS correction is not global convergence or real accuracy'])
