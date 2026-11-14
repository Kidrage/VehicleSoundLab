"""Known AM/FM checks through the actual frozen acoustic-phase observer."""
import numpy as np
from idle_conditioned_detail_v1.features import phases
from .observe import SELECTED,observe,statistics


def run():
    frequencies=np.array([37.19,75.31,112.73,150.12,187.69,225.43,262.77,284.61,299.84,359.43,375.16,472.63,486.93])
    amplitudes=np.array([.016,.08,.075,.0105,.039,.0095,.0104,.0136,.0142,.003,.0028,.0044,.0021])
    n=144000;t=np.arange(n)/48000
    offset=np.linspace(-.9,.7,13);base=2*np.pi*t[:,None]*frequencies+offset
    w=.5-.5*np.cos(2*np.pi*np.arange(9600)/9600)
    results=[];arrays={}
    for label,AM,FM in [('constant',False,False),('nonlinearFM',False,True),('AM',True,False),('combined',True,True)]:
        angle=base.copy();amplitude=np.tile(amplitudes,(n,1))
        if FM:
            depth=np.array([.9,1.2,.7]);rate=np.array([1.6,1.3,1.1])
            angle[:,SELECTED]-=depth/rate*np.cos(2*np.pi*t[:,None]*rate)
        if AM:amplitude[:,SELECTED]*=1+np.array([.2,.15,.18])*np.cos(2*np.pi*.8*t[:,None]+[.3,-.8,1.1])
        audio=np.column_stack([np.sum(amplitude*np.cos(angle),axis=1)]*2)
        z=np.exp(1j*angle[:,SELECTED])
        measured=phases(audio[:,0],frequencies[SELECTED])
        truth=observe(audio,frequencies,z);actual=observe(audio,frequencies,measured);fixed=observe(audio,frequencies)
        expected=np.array([(w[:,None]*amplitude[first:first+9600,SELECTED]).sum(axis=0)/w.sum() for first in actual['starts']])
        truth_error=float(abs(abs(truth['coefficients'][:,SELECTED])/expected-1).max())
        error=float(abs(abs(actual['coefficients'][:,SELECTED])/expected-1).max())
        phase_error=float(np.quantile(abs(np.angle(measured[12000:-12000]/z[12000:-12000])),.95))
        summary,values=statistics(actual['coefficients']);fixed_summary,_=statistics(fixed['coefficients'])
        if not AM:
            assert truth_error<1e-10,(label,'true-phasor exact amplitude',truth_error)
            assert max(summary['raw_log_std'])<=.003,(label,'false AM std',summary['raw_log_std'])
            assert error<=.005,(label,'false AM relative error',error)
        else:assert error<=.003,(label,'weighted AM amplitude error',error)
        assert phase_error<=.05,(label,'phase p95',phase_error)
        results.append(dict(label=label,true_phasor_amplitude_error=truth_error,actual_amplitude_error=error,
            phase_error_p95_rad=phase_error,aware_log_std=summary['raw_log_std'],fixed_log_std=fixed_summary['raw_log_std']))
        arrays[label+'_audio']=audio;arrays[label+'_phasors']=measured;arrays[label+'_truth_phasors']=z
        arrays[label+'_expected_amplitudes']=expected;arrays[label+'_coefficients']=actual['coefficients']
    # Deliberately unmodeled adjacent component; measurement is not source identification.
    angle=base.copy();x=np.sum(amplitudes*np.cos(angle),axis=1)+.02*np.cos(2*np.pi*(frequencies[1]+8)*t+.3)
    audio=np.column_stack([x,x]);measured=phases(x,frequencies[SELECTED])
    observation=observe(audio,frequencies,measured);summary,_=statistics(observation['coefficients'])
    results.append(dict(label='adjacent_unmodeled_counterexample',aware_log_std=summary['raw_log_std'],
                        scope='Apparent amplitude can be caused by an unmodeled neighbor; not physical combustion AM'))
    arrays.update(frequencies=frequencies,amplitudes=amplitudes,neighbor_audio=audio,neighbor_phasors=measured,
                  neighbor_coefficients=observation['coefficients'])
    return dict(result='known_AM_FM_observer_controls_passed',cases=results,physical_source_identified=False),arrays
