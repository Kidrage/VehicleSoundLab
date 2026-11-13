"""Known-coordinate linear operator tests, plus explicit nonidentifiability and clock error."""
import numpy as np
from scipy.special import jv
from .sidebands import observe,parity


def fixtures(rate=48000):
    t=np.arange(rate)/rate-.5;f=np.array([75.25]);q=np.array([.3]);theta=2*np.pi*(f[0]*t+.5*q[0]*t*t)
    c=.5*np.exp(.2j);carrier=(c*np.exp(1j*theta)).real
    am=.2*np.exp(.6j);pm=.1*np.exp(.4j);neighbor=.2*np.exp(.8j)
    zeros=0j
    yield dict(id='unmodulated',audio=carrier,frequency=f,chirp=q,expected=(c,zeros,zeros),exact_span=True)
    x=(1+.4*np.cos(2*np.pi*3*t+.6))*carrier
    yield dict(id='am',audio=x,frequency=f,chirp=q,expected=(c,c*am,c*np.conj(am)),exact_span=True)
    x=carrier-(c*np.exp(1j*theta)).imag*.2*np.cos(2*np.pi*3*t+.4)
    yield dict(id='quadrature',audio=x,frequency=f,chirp=q,expected=(c,1j*c*pm,1j*c*np.conj(pm)),exact_span=True)
    x=.5*np.cos(theta+.2+.2*np.cos(2*np.pi*3*t+.4))
    yield dict(id='true_phase_modulation',audio=x,frequency=f,chirp=q,
        expected=(c*jv(0,.2),1j*c*jv(1,.2)*np.exp(.4j),1j*c*jv(1,.2)*np.exp(-.4j)),exact_span=False)
    # A single independent upper tone has equal AM/quadrature parity magnitudes.
    x=carrier+(neighbor*np.exp(1j*(theta+2*np.pi*3*t))).real
    yield dict(id='one_independent_upper',audio=x,frequency=f,chirp=q,expected=(c,neighbor,zeros),exact_span=True)
    # This separate three-tone construction is algebraically identical to the AM fixture.
    x=carrier+(c*am*np.exp(1j*(theta+2*np.pi*3*t))).real+(c*np.conj(am)*np.exp(1j*(theta-2*np.pi*3*t))).real
    yield dict(id='independent_pair_equal_to_am',audio=x,frequency=f,chirp=q,expected=(c,c*am,c*np.conj(am)),exact_span=True)


def controls(rate=48000):
    t=np.arange(rate)/rate-.5;rows=[];am_audio=None;identity_error=None
    for case in fixtures(rate):
        fitted,measured=observe(case['audio'],case['frequency'],case['chirp'],t)
        expected=parity(*case['expected']);errors=[]
        for key in ('central','upper','lower'):
            errors.append(float(abs(np.array(measured['parity'][0][key])-np.array(expected[key])).max()))
        for key in ('am_relative','quadrature_relative'):
            errors.append(float(abs(np.array(measured['parity'][0][key])-np.array(expected[key])).max()))
        relative=float(np.linalg.norm(fitted-case['audio'])/np.linalg.norm(case['audio']))
        tolerance=1e-10 if case['exact_span'] else 1e-5
        passed=max(errors)<=tolerance and measured['gradient_infinity']<=1e-10
        if case['exact_span']:passed=passed and relative<=1e-10
        if case['id']=='am':am_audio=case['audio']
        if case['id']=='independent_pair_equal_to_am':identity_error=float(abs(case['audio']-am_audio).max())
        rows.append(dict(id=case['id'],passed=bool(passed),exact_span=case['exact_span'],
            max_coefficient_or_parity_error=max(errors),waveform_relative_error=relative,measurement=measured))
    case=next(fixtures(rate));_,mismatch=observe(case['audio'],case['frequency']+.5,case['chirp'],t)
    _,scaled=observe(case['audio']*7,case['frequency'],case['chirp'],t)
    gain_error=max(abs(np.array(scaled['parity'][0][key])-np.array(rows[0]['measurement']['parity'][0][key])).max() for key in ('am_relative','quadrature_relative'))
    zero=parity(0j,1+.3j,.2-.1j)
    return dict(passed=all(r['passed'] for r in rows) and identity_error<=1e-12 and gain_error<=1e-10 and zero['am_relative'] is None and zero['quadrature_relative'] is None,
        cases=rows,independent_pair_AM_wave_identity_error=identity_error,gain_invariance_error=float(gain_error),
        zero_reference=zero,half_native_bin_coordinate_error=dict(frequency_error_Hz=.5,measurement=mismatch),
        phase_estimator_initialized_or_qualified=False,
        limits=['Known phase is an explicit operator-test coordinate; no phase estimator was run or truth-initialized',
            'AM and paired independent tones can be exactly identical; parity is not a physical-source classifier',
            'A wrong coordinate can create apparent AM/quadrature detail on an unmodulated tone'])
