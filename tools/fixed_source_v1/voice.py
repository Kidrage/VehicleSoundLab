"""One renderer: all timbre differences come from the supplied profile."""
import numpy as np
from scipy import signal
from idle_modal_v1.modal import render as render_modal
from idle_texture_v2.dynamics import states,gains
from sustain_osc_v1.oracle import Gaussian


def render(profile,frames,seed,*,ratio=1.,amount=0.):
    if not isinstance(frames,int) or frames<1:
        raise ValueError('Positive integer frame count required')
    if not np.isfinite(ratio) or ratio<=0 or not np.isfinite(amount) or not 0<=amount<=1:
        raise ValueError('Finite positive ratio and0..1 amount required')
    main=render_modal(profile['modal'],frames,profile['sample_rate'],ratio)
    texture=np.zeros_like(main)
    envelope=dict(profile['envelope'],strength=profile['envelope']['strength']*amount)
    state,_=states(envelope,frames,seed);gain=gains(envelope,state,frames)
    count=frames+profile['warmup_frames']
    for i,model in enumerate(profile['kernels']):
        rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
        noise=np.fromiter((rng.next() for _ in range(count)),dtype=float,count=count)
        y=signal.oaconvolve(noise,np.asarray(model['taps']))[profile['warmup_frames']:count]*model['gain']
        texture+=y[:,None]*np.array([[1.,model['right_over_left']]])*gain[:,i,None]
    return main+texture,main,texture


def controls():
    # Analytic two-tone stereo fixture and known short filter, unrelated to recordings.
    rate=48000;frames=2051
    profile=dict(sample_rate=rate,warmup_frames=12,
        modal=dict(frequencies_hz=[83.17,193.41],amplitude_LR=[[.2,.1],[.03,.04]],
            initial_phase_LR=[[.1,.3],[.2,-.1]]),
        kernels=[dict(taps=[.8,.6],gain=.01,right_over_left=.7)],
        envelope=dict(covariance=[[.04]],alpha=.7,hop_frames=960,strength=.5))
    actual,main,detail=render(profile,frames,149921,ratio=1.1,amount=0)
    t=np.arange(frames)/rate
    oracle=sum(np.array(a)*np.cos(2*np.pi*f*1.1*t[:,None]+np.array(p)) for f,a,p in zip(
        profile['modal']['frequencies_hz'],profile['modal']['amplitude_LR'],profile['modal']['initial_phase_LR']))
    assert abs(main-oracle).max()<1e-12
    rng=Gaussian(149921^0x9E3779B97F4A7C15)
    noise=np.array([rng.next() for _ in range(frames+12)])
    expected=np.convolve(noise,[.8,.6])[12:frames+12]*.01
    assert abs(detail-expected[:,None]*np.array([[1.,.7]])).max()<1e-12
    assert actual.shape==(frames,2)
    for ratio,amount in [(0,0),(float('nan'),0),(1,-.1),(1,1.1),(1,float('inf'))]:
        try:render(profile,frames,149921,ratio=ratio,amount=amount)
        except ValueError:pass
        else:raise AssertionError('Invalid controls accepted')
    return dict(analytic_modal_error=float(abs(main-oracle).max()),direct_filter_oracle=True,
        duration_independent_of_pitch=True,invalid_controls_rejected=True)
