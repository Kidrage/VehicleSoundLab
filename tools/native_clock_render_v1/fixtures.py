"""Declared analytic clocks and stereo sources, not engine presets."""
import numpy as np


def specs():
    base=dict(root=64.,slope=0.,cubic=0.,pm=0.,delay=0.,am=0.,mono=False,silent=False,zero=False,all_orders=False)
    variants=[('zero',dict(zero=True)),('mono',dict(mono=True)),('unequal_phase',{}),
        ('silent_right',dict(silent=True)),('linear_AM',dict(am=.08)),
        ('rising_clock',dict(root=56.,slope=20.)),('falling_clock',dict(root=85.,slope=-30.)),
        ('common_PM',dict(pm=.035)),('delayed_right',dict(root=62.,slope=10.,delay=.00035)),
        ('cubic_chirp',dict(root=54.,slope=18.,cubic=6.)),
        ('near_Nyquist',dict(root=128.)),('pure_stopband',dict(root=128.)),
        ('full288',dict(root=128.,all_orders=True))]
    return [(name,dict(base,**change)) for name,change in variants]


def phase(t,s):
    return s['root']*t+.5*s['slope']*t*t+s['cubic']*t**3/3+s['pm']*np.sin(2*np.pi*.8*t)


def inverse(p,s):
    t=p/s['root']
    for _ in range(12):
        derivative=s['root']+s['slope']*t+s['cubic']*t*t+s['pm']*2*np.pi*.8*np.cos(2*np.pi*.8*t)
        t=t-(phase(t,s)-p)/derivative
    return t


def active(name):
    if name=='full288':return np.arange(1,289)
    if name=='near_Nyquist':return np.array([152,160,172,184,192,219])
    if name=='pure_stopband':return np.array([203])
    return np.array([3,5,7,71,127,193,249])


def coefficients(p,s,name,center):
    p=np.asarray(p);out=np.zeros((len(p),288,2),complex)
    ids=active(name)
    for i,h in enumerate(ids):
        amplitude=(.07/(1+.02*h) if name=='full288' else .09/(1+.4*i))
        if s['zero']:amplitude=0.
        out[:,h-1,0]=amplitude*(1+s['am']*(p-center))*np.exp(.13j*h)
        t=inverse(p,s)
        delay_phase=phase(t-s['delay'],s)-p
        out[:,h-1,1]=.61*amplitude*(1-.75*s['am']*(p-center))*np.exp(1j*(.13*h+.37+2*np.pi*h*delay_phase))
    if s['mono']:out[:,:,1]=out[:,:,0]
    if s['silent']:out[:,:,1]=0
    return out


def make(name,s,count=4096):
    first=.25;stop=first+(count-1)/48000
    low=int(np.floor(phase(first,s)))-2;high=int(np.ceil(phase(stop,s)))+2
    p=low+np.arange((high-low)*1024+1)/1024
    source_seconds=17+inverse(p,s)
    positions=[0];steps=[197,306,297,291,257]
    while positions[-1]+steps[(len(positions)-1)%len(steps)]<len(p)-1:
        positions.append(positions[-1]+steps[(len(positions)-1)%len(steps)])
    positions=np.array(positions+[len(p)-1])
    center=float(phase((first+stop)/2,s))
    nodes=coefficients(p[positions],s,name,center)
    return dict(source_seconds=source_seconds,positions=positions,orders=np.arange(1,289),nodes=nodes,
        native_start=np.array(17+first),count=np.array(count),phase_origin=np.array(low),center=np.array(center))
