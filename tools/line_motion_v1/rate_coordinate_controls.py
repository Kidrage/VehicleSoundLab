"""Existing frequency controls and unchanged harmonic rise/fall recovery."""
import numpy as np
from .chirp_limit_controls import fixtures
from .local_chirps import evaluate
from .peaks import native_peaks
from .peak_controls import peak_controls
from .rate_coordinates import rate_bounds,fit_channel,rate_coordinates


def controls(rate=48000):
    prior=peak_controls(observer=rate_coordinates);t=np.arange(rate)/rate-.5;rows=[];invariance=0.
    for case in fixtures(rate):
        observed=native_peaks(np.column_stack((case['audio'],case['audio'])),rate,case['labels'])
        nominal=observed['selected_native_bin_Hz'][:,0].astype(float)
        parameters,fit=fit_channel(case['audio'],rate,nominal);m=len(nominal)
        frequency=float(abs(nominal+parameters[:m]-case['frequency']).max())
        chirp=float(abs(parameters[m:2*m]-case['chirp']).max())
        relative=float(np.linalg.norm(evaluate(parameters,nominal,t)[0]-case['audio'])/np.linalg.norm(case['audio']))
        original=rate_bounds(nominal,nominal[0]);converted=rate_bounds(nominal,nominal[2],2*nominal[2]/nominal[0])
        invariance=max(invariance,float(abs(original-converted).max()))
        rows.append(dict(id=case['id'],fit=fit,max_frequency_error_Hz=frequency,max_chirp_error_Hz_per_s=chirp,
            waveform_relative_error=relative,passed=bool(fit['success'] and not any(fit['at_bound']) and frequency<=.01 and chirp<=.01 and relative<=1e-6)))
    return dict(passed=prior['passed'] and all(row['passed'] for row in rows) and invariance<=1e-12,
        prior_controls=prior,cases=rows,reference_conversion_bound_error=invariance,
        limits=['Known local independent chirps only, not shared-phase or physical RPM qualification',
            'Equal fractional-rate bound is an engineering prior and does not enforce harmonic motion'])
