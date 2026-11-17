"""Sparse piecewise-linear frequency control with exact continuous phase integration."""
import numpy as np

RATE=48000


def validate(profile):
    required={'schema','duration_seconds','seconds','frequencies_hz','initial_phase'}
    if not isinstance(profile,dict) or set(profile)!=required or profile['schema']!='vsl.sparse-acoustic-motion/1':
        raise ValueError('Sparse acoustic motion schema required')
    t=np.asarray(profile['seconds'],dtype=float);f=np.asarray(profile['frequencies_hz'],dtype=float)
    if t.ndim!=1 or f.shape!=t.shape or not 2<=len(t)<=9 or not np.isfinite(t).all() or not np.isfinite(f).all():
        raise ValueError('Two through nine finite time/frequency controls required')
    duration=profile['duration_seconds'];phase=profile['initial_phase']
    if not np.isfinite([duration,phase]).all() or duration<=0 or t[0]!=0 or t[-1]!=duration or np.any(np.diff(t)<=0) or np.any(f<=0) or np.any(f>=24000):
        raise ValueError('Increasing full-event controls and frequencies below Nyquist required')
    return t,f


def phase(profile,frames,pitch=1.,time_scale=1.,first_frame=0):
    t,f=validate(profile)
    if type(frames) is not int or frames<1 or type(first_frame) is not int or first_frame<0:
        raise ValueError('Positive native frame count and nonnegative origin required')
    if not np.isfinite([pitch,time_scale]).all() or min(pitch,time_scale)<=0 or np.max(f)*pitch>=24000:
        raise ValueError('Positive time/pitch controls with sub-Nyquist frequency required')
    # The physical output time is scaled independently from pitch. Analytic
    # integration avoids resetting phase at knots or at host block boundaries.
    clock=(first_frame+np.arange(frames))/RATE/time_scale
    if clock[-1]>=t[-1]+1e-12:raise ValueError('Requested samples leave authored event support')
    interval=np.clip(np.searchsorted(t,clock,side='right')-1,0,len(t)-2)
    area=np.r_[0.,np.cumsum(.5*(f[:-1]+f[1:])*np.diff(t))]
    dt=clock-t[interval]
    slope=np.diff(f)/np.diff(t)
    cycles=area[interval]+f[interval]*dt+.5*slope[interval]*dt*dt
    return profile['initial_phase']+2*np.pi*pitch*time_scale*cycles


def from_points(points):
    if len(points)<5:raise ValueError('At least five supported observations required')
    observed=np.array([p['centre_seconds'] for p in points]);hz=np.array([p['hz'] for p in points])
    if not np.all(np.diff(observed)>0):raise ValueError('Increasing support required')
    seconds=np.linspace(0,observed[-1]-observed[0],min(9,len(points)))
    frequencies=np.interp(seconds,observed-observed[0],hz)
    profile=dict(schema='vsl.sparse-acoustic-motion/1',duration_seconds=float(seconds[-1]),
        seconds=seconds.tolist(),frequencies_hz=frequencies.tolist(),initial_phase=0.)
    validate(profile)
    return profile


def design(profile,frames,knots=1):
    if type(knots) is not int or not 1<=knots<=5:raise ValueError('One through five amplitude controls required')
    angle=phase(profile,frames)
    t=np.arange(frames)/RATE
    times=np.linspace(0,profile['duration_seconds'],knots) if knots>1 else np.array([0.])
    hats=np.column_stack([np.interp(t,times,row) for row in np.eye(knots)])
    return np.column_stack((np.cos(angle)[:,None]*hats,np.sin(angle)[:,None]*hats)),times
