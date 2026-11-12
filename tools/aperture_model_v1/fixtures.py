"""Analytic curves independent of the inverse spline and aperture code."""
import numpy as np


def make(case,plan):
    cycle=plan['samples_per_cycle']
    time=np.arange(round(plan['cycles']*cycle))/cycle
    epsilon=np.zeros_like(time)
    if case['phase']:
        epsilon=.055*np.exp(-((time-18)/1.3)**2)-.035*np.exp(-((time-21)/.9)**2)+.012*np.sin(2*np.pi*.077*time)
        epsilon-=epsilon[0]
    audio=np.zeros((len(time),2))
    orders=plan['source_orders']+plan['heldout_orders']
    for index,order in enumerate(orders):
        if case.get('single') and order!=5:
            continue
        amplitude=.022*(1+.15*np.cos(index*.31))
        if order in (2,3,5,7):
            amplitude=.045
        envelope=np.ones_like(time)
        if case['amplitude']:
            envelope+=.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index)
        angle=2*np.pi*order*(time+epsilon)+.37*order+.013*order*order
        if case.get('contaminated_order')==order:
            angle+=.6*np.sin(2*np.pi*.17*time)
        audio[:,0]+=amplitude*envelope*np.cos(angle)
        audio[:,1]+=.82*amplitude*envelope*np.cos(angle+.17+.021*order)
    rng=np.random.default_rng(910284)
    audio+=case['noise']*rng.normal(size=audio.shape)
    return time,audio,epsilon


def complex_ambiguity(time):
    first=.04*np.sin(.4*time)
    second=.06*np.exp(-((time-18)/2)**2)
    original=np.zeros_like(time,dtype=complex)
    equivalent=np.zeros_like(time,dtype=complex)
    for order,coefficient in ((2,.045*np.exp(.2j)),(3,.04*np.exp(.7j)),(5,.03*np.exp(-.6j))):
        original+=coefficient*np.exp(2j*np.pi*order*(time+first))
        changed=coefficient*np.exp(2j*np.pi*order*(first-second))
        equivalent+=changed*np.exp(2j*np.pi*order*(time+second))
    return dict(maximum_sample_difference=float(abs(original-equivalent).max()),
        maximum_phase_difference_cycles=float(abs(first-second).max()),
        identifiable_with_unrestricted_complex_envelopes=False)
