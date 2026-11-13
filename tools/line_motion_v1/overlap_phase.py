"""Compare independent local complex trajectories without aligning their phases."""
import numpy as np


def adjacent_overlaps(rows,rate):
    pairs=[];unconnected=[]
    for i in range(len(rows)-1):
        a=np.rint(np.array(rows[i]['source_seconds'])*rate).astype(int)
        b=np.rint(np.array(rows[i+1]['source_seconds'])*rate).astype(int)
        assert a[0]<b[0] and a[1]<=b[1]
        first=max(a[0],b[0]);stop=min(a[1],b[1])
        item=dict(left_window=i,right_window=i+1,first_sample=int(first),stop_sample=int(stop))
        (pairs if stop>first else unconnected).append(item)
    return pairs,unconnected


def line_from_fit(fit,seconds,index):
    nominal=np.array(fit['nominal_Hz']);m=len(nominal);p=np.array(fit['fitted_parameters'])
    assert len(p)==4*m+1 and np.isfinite(p).all()
    return dict(centre_seconds=float(np.mean(seconds)),frequency_Hz=float(nominal[index]+p[index]),
        chirp_Hz_per_s=float(p[m+index]),a=float(p[2*m+index]),b=float(p[3*m+index]),
        nominal_bin_Hz=float(nominal[index]),success=fit['success'],at_bound=fit['at_bound'][index])


def trajectory(line,time):
    t=time-line['centre_seconds']
    angle=2*np.pi*(line['frequency_Hz']*t+.5*line['chirp_Hz_per_s']*t*t)
    return complex(line['a'],-line['b'])*np.exp(1j*angle)


def compare(left,right,samples,rate):
    assert len(samples)>0 and np.all(np.diff(samples)==1)
    time=samples/rate;one=trajectory(left,time);two=trajectory(right,time)
    a=abs(complex(left['a'],-left['b']));b=abs(complex(right['a'],-right['b']))
    delta_frequency=(right['frequency_Hz']+right['chirp_Hz_per_s']*(time-right['centre_seconds'])
        -left['frequency_Hz']-left['chirp_Hz_per_s']*(time-left['centre_seconds']))
    result=dict(left=left,right=right,samples=len(samples),amplitude_left=a,amplitude_right=b,
        frequency_difference_rms_Hz=float(np.sqrt(np.mean(delta_frequency**2))),
        frequency_difference_max_Hz=float(abs(delta_frequency).max()),
        chirp_difference_Hz_per_s=right['chirp_Hz_per_s']-left['chirp_Hz_per_s'],
        complex_difference_relative_rms=None if a*a+b*b==0 else float(np.sqrt(np.mean(abs(two-one)**2)/(.5*(a*a+b*b)))),
        phase_defined=a>0 and b>0)
    if not result['phase_defined']:
        result.update(phase_status='undefined_zero_component',unit_phasor_rms_distance=None,
            wrapped_phase_rms_cycles=None,wrapped_phase_max_cycles=None,midpoint_phase_difference_cycles=None,
            continuous_phase_rms_cycles=None,continuous_phase_max_cycles=None)
    else:
        ratio=(two/b)*np.conj(one/a);wrapped=np.angle(ratio)/(2*np.pi)
        # Select a 2pi branch using the actual midpoint difference; retain its constant offset.
        midpoint=.5*(samples[0]+samples[-1])/rate
        z1=trajectory(left,np.array([midpoint]))[0]/a;z2=trajectory(right,np.array([midpoint]))[0]/b
        middle=float(np.angle(z2*np.conj(z1))/(2*np.pi))
        fd=(right['frequency_Hz']+right['chirp_Hz_per_s']*(midpoint-right['centre_seconds'])
            -left['frequency_Hz']-left['chirp_Hz_per_s']*(midpoint-left['centre_seconds']))
        dt=time-midpoint;continuous=middle+fd*dt+.5*result['chirp_difference_Hz_per_s']*dt*dt
        result.update(phase_status='observed_modulo_integer_cycle_NOT_aligned',
            unit_phasor_rms_distance=float(np.sqrt(np.mean(abs(two/b-one/a)**2))),
            wrapped_phase_rms_cycles=float(np.sqrt(np.mean(wrapped**2))),wrapped_phase_max_cycles=float(abs(wrapped).max()),
            midpoint_phase_difference_cycles=middle,continuous_phase_rms_cycles=float(np.sqrt(np.mean(continuous**2))),
            continuous_phase_max_cycles=float(abs(continuous).max()))
    return result,one,two
