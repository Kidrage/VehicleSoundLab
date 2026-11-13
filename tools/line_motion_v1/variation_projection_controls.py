"""Fixed operator contracts and common-cubic / independent-neighbor fit examples."""
import numpy as np
from .variation_projection import observe,frequency_disagreement
from .overlap_phase import line_from_fit
from .peaks import native_peaks
from .local_precision import fit_channel
from .local_chirps import evaluate


def fixtures(rate=48000):
    u=np.arange(3*rate//2)/rate-.75;n=np.array([2,3,5]);amp=np.array([.5,.4,.3]);phase=np.array([.2,.5,.8])
    for name,r,neighbor in [('common_cubic',.24,False),('independent_neighbor',0.,True)]:
        root=37.6*u+.15*u*u+r*u**3/6
        main=(amp*np.cos(2*np.pi*root[:,None]*n+phase)).sum(axis=1)
        audio=main+.18*np.cos(2*np.pi*(82.3*u-.1*u*u)+.1)
        if neighbor:audio+=.08*np.cos(2*np.pi*78.2*u+.7)
        yield dict(id=name,audio=audio,root_cubic_coefficient=r,neighbor_added=neighbor)


def controls(rate=48000):
    time=np.arange(rate//2,rate)/rate;g=.12+.6*(time-.75);n=np.array([2.,3.,5.])
    common,_=observe(g[:,None]*n);single,_=observe(np.column_stack((g,0*g,0*g)));zero,_=observe(np.zeros((len(time),3)))
    error=max(abs(common['harmonic_hypothesis']['residual_squared_fraction']),
        abs(common['equal_Hz']['residual_squared_fraction']-(1-100/114)),
        abs(single['harmonic_hypothesis']['residual_squared_fraction']-(1-4/38)),
        abs(single['equal_Hz']['residual_squared_fraction']-2/3),
        max(common['harmonic_hypothesis']['omitted_line_prediction_rms_error_Hz']))
    assert error<=1e-10 and all(x['residual_squared_fraction'] is None for x in zero.values())
    # Same samples can be produced with one shared expression or independent per-line programs.
    u=np.arange(3*rate//2)/rate-.75;root=37.6*u+.15*u*u+.24*u**3/6
    one=sum(a*np.cos(2*np.pi*k*root+p) for a,k,p in zip([.5,.4,.3],n,[.2,.5,.8]))
    independent=sum(a*np.cos(2*np.pi*((k*37.6)*u+.5*(k*.3)*u*u+(k*.24)*u**3/6)+p)
        for a,k,p in zip([.5,.4,.3],n,[.2,.5,.8]))
    identity=float(abs(one-independent).max());assert identity<=1e-10
    cases=[]
    for case in fixtures(rate):
        fits=[];errors=[]
        for start in (0,rate//2):
            part=case['audio'][start:start+rate]
            measured=native_peaks(np.column_stack((part,part)),rate,[75,113,188,82])
            nominal=measured['selected_native_bin_Hz'][:,0].astype(float);assert np.all(nominal>0)
            parameters,fit=fit_channel(part,rate,nominal);fits.append(fit)
            wave=evaluate(parameters,nominal,np.arange(rate)/rate-.5)[0]
            errors.append(float(np.linalg.norm(wave-part)/np.linalg.norm(part)))
        left=[line_from_fit(fits[0],[0.,1.],j) for j in range(3)]
        right=[line_from_fit(fits[1],[.5,1.5],j) for j in range(3)]
        d=frequency_disagreement(left,right,time);observed,_=observe(d)
        cases.append(dict(id=case['id'],fits=fits,waveform_relative_errors=errors,observations=observed,
            passed=bool(all(f['success'] and np.isfinite(f['fitted_parameters']).all() for f in fits)),
            bounds=[fit['at_bound'] for fit in fits],truth_used_as_fit_initialization=False))
    return dict(passed=all(case['passed'] for case in cases),operator_error=error,common_operator=common,
        first_slot_operator=single,zero_operator=zero,independent_program_identity_error=identity,cases=cases,
        limits=['Known fitted examples are descriptive; no classification threshold chosen from their signatures',
            'Quadratic fits need not exactly represent cubic phase or omitted neighbors; waveform errors are retained',
            'Matching relative variation does not identify a physical common source or recover its phase'])
