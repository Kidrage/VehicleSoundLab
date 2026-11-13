"""Analytic observations and deliberately nonidentifying counterexamples."""
import numpy as np
from .moments import observe,group_observation


def controls(rate=48000,observer=observe):
    time=np.arange(rate)/rate
    nominal=np.array([75.,112.,187.,82.,37.])
    rows=[]
    fixed=np.array([75.19,112.27,187.39,82.13,37.23])
    errors=[]
    for frequency,carrier in zip(fixed,nominal):
        x=.2*np.cos(2*np.pi*frequency*time+.31)
        value=observer(np.column_stack((x,.8*x)),rate,[carrier])
        errors.append(float(abs(value['frequency_Hz']-frequency).max()))
    rows.append(dict(id='detuned_real_sines',passed=max(errors)<=.001,max_frequency_error_Hz=max(errors)))
    # Generate each chirp separately; quadratic analytic phase is distinct from the observer.
    errors=[]
    for order,carrier in zip([2,3,5,2.2,1],nominal):
        initial=37.35*order if order!=2.2 else 81.9
        slope=.12*order if order!=2.2 else .07
        x=.2*np.cos(2*np.pi*(initial*time+.5*slope*time**2)+.6)
        value=observer(np.column_stack((x,.7*x)),rate,[carrier])
        errors.append(float(abs(value['frequency_Hz']-(initial+slope*.5)).max()))
    rows.append(dict(id='local_linear_chirps',passed=max(errors)<=.01,max_frequency_error_Hz=max(errors)))
    x=.3*(1+.4*np.cos(2*np.pi*3*time))*np.cos(2*np.pi*75.19*time+.9)
    value=observer(np.column_stack((x,x)),rate,[75.])
    error=float(abs(value['frequency_Hz']-75.19).max())
    rows.append(dict(id='AM_only_fixed_frequency',passed=error<=.001,max_frequency_error_Hz=error))
    # Original5 observations: first3 have a common moving family, order1 is withheld;
    # the82Hz line is intentionally a separate fixed oscillator, not a missing observation.
    phase=37.35*time+.5*.12*time**2
    x=sum(a*np.cos(2*np.pi*order*phase+p) for order,a,p in [(1,.15,.2),(2,.5,.6),(3,.4,.9),(5,.3,1.2)])
    x+=.18*np.cos(2*np.pi*82*time+.7)
    value=observer(np.column_stack((x,.9*x)),rate,nominal)
    expected=np.array([2,3,5,0,1])*(37.35+.12*.5);expected[3]=82
    error=float(abs(value['frequency_Hz']-expected[:,None]).max())
    grouped=group_observation(value['frequency_Hz'])
    rows.append(dict(id='shared_chirp_plus_independent_line',passed=error<=.01 and bool(value['supported'].all()),
        max_frequency_error_Hz=error,order1_prediction_error_Hz=grouped['heldout_order1_error_Hz'].tolist(),
        independent_line_mismatch_Hz=grouped['extra_11_over_5_error_Hz'].tolist()))
    x=.5*np.cos(2*np.pi*75.19*time+.1)
    value=observer(np.column_stack((x,x)),rate,nominal)
    rows.append(dict(id='single_line_does_not_supply_three_anchors',
        passed=bool(value['supported'][0].all() and not value['supported'][1:].any()),
        supported=value['supported'].tolist(),relative_db=value['relative_db'].tolist()))
    # No "period accepted" gate is applied to either negative observation.
    x=sum(a*np.cos(2*np.pi*f*time+p) for a,f,p in zip([.5,.4,.3,.2,.15],fixed,[.1,.4,.8,.3,.6]))
    other=observer(np.column_stack((x,x)),rate,nominal)
    noise=np.random.default_rng(731091).normal(0,.1,(rate,2))
    random=observer(noise,rate,nominal)
    return dict(passed=all(r['passed'] for r in rows),cases=rows,
        nonharmonic_observation={k:v.tolist() for k,v in group_observation(other['frequency_Hz']).items()},
        noise_counterexample={k:random[k].tolist() for k in ('frequency_Hz','supported','relative_db')},
        scope='Local frequency observation controls only; supported moments are not a physical-period detector')
