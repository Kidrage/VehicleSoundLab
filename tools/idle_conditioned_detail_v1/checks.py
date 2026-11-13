"""Small independent contracts before inspecting real conditional structure."""
import numpy as np
from .features import average,phases
from .model import fit,assess,gain


def controls():
    rate=48000;n=144000;t=np.arange(n)/rate
    freq=np.array([75.17,112.61,187.73]);offset=np.array([.2,-.6,1.1])
    z=np.exp(1j*(2*np.pi*t[:,None]*freq+offset))
    feature=average(np.column_stack((z.real,z.imag)),48)
    coefficient=np.array([[1.,.8],[.14,-.12],[-.09,.08],[.11,.05],[.06,.09],[.04,-.06],[-.05,.04]])
    power=np.column_stack((np.ones(len(feature)),feature))@coefficient
    model=fit(feature,power);expected=coefficient/power.mean(axis=0)
    error=float(abs(np.asarray(model['coefficients'])-expected).max());assert error<1e-12
    t2=t+3.123;z2=np.exp(1j*(2*np.pi*t2[:,None]*freq+offset))
    f2=average(np.column_stack((z2.real,z2.imag)),48)
    p2=np.column_stack((np.ones(len(f2)),f2))@coefficient
    assert max(assess(model,f2,p2)['conditional_mse'])<1e-24
    unrelated=np.ones_like(p2);unrelated[:,0]+=.05*np.cos(2*np.pi*np.arange(len(p2))*.027)
    assert max(assess(model,f2,unrelated)['relative_mse_improvement'])<0
    # Scale of observed audio cannot change normalized conditional power law.
    scaled=fit(feature,power*.13)
    assert abs(np.asarray(scaled['coefficients'])-model['coefficients']).max()<1e-12
    # A common independent feature rotation simply changes regression coordinates.
    rotated=z*np.exp(.37j);fr=average(np.column_stack((rotated.real,rotated.imag)),48)
    mr=fit(fr,power)
    assert abs(gain(mr,rotated,.7)-gain(model,z,.7)).max()<1e-12
    invalid=dict(model,positive=False)
    try:gain(invalid,z,1)
    except ValueError:pass
    else:raise AssertionError('Nonpositive model accepted')
    # Known off-grid mixture and slow chirp through the ACTUAL phase observer.
    tests=[]
    for chirp in [0.,.3]:
        truth=np.exp(1j*(2*np.pi*(t[:,None]*freq+.5*chirp*t[:,None]**2)+offset))
        audio=truth.real@np.array([.1,.08,.06])+.01*np.cos(2*np.pi*284.77*t)
        measured=phases(audio,freq);angle=np.angle(measured[12000:-12000]/truth[12000:-12000])
        maximum=float(np.quantile(abs(angle),.95));assert maximum<.035
        tests.append(dict(chirp_hz_per_second=chirp,phase_p95_radians=maximum))
    # Rectangle average has a known complex sinc response (not center-sampling).
    theory=np.exp(1j*(2*np.pi*freq*(47/2)/rate+offset))*np.sinc(48*freq/rate)/np.sinc(freq/rate)
    avg_error=float(abs(average(z,48)[0]-theory).max());assert avg_error<1e-12
    return dict(coefficient_max_error=error,known_check_prediction=True,unrelated_fails_transfer=True,
        positive_model_required=True,phase_rotation_invariance=True,scale_invariance=True,
        actual_phase_observer_known_cases=tests,complex_average_error=avg_error,
        physical_engine_phase_qualification=False)

