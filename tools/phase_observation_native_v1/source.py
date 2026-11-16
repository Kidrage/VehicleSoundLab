"""Continuous extension of the saved analytic control metadata."""
import numpy as np


def coordinate(seconds,geometry,depth=0.):
    t=np.asarray(seconds);start=geometry['normalized_start'];f=geometry['clock_frequency_Hz']
    phase=t-start+depth*(np.cos(2*np.pi*f*start)-np.cos(2*np.pi*f*t))/(2*np.pi*f)
    return phase*geometry['root_hz']*geometry['samples_per_cycle']


def evaluate(spec,q):
    q=np.asarray(q);audio=np.zeros((len(q),2));kind=spec['kind']
    for j,order in enumerate(spec['orders']):
        carrier=2*np.pi*np.remainder(q,1024)*order/1024
        modulation=2*np.pi*q/(7*1024)
        for ch in (0,1):
            gain=np.ones(len(q));angle=carrier+spec['phases'][j,ch]
            if j==1 and kind in ('common_AM','differential_AM'):
                sign=1 if kind=='common_AM' or ch==0 else -1
                gain+=sign*spec['modulation_depth']*np.cos(modulation)
            if j==1 and kind in ('common_PM','relative_PM'):
                sign=1 if kind=='common_PM' or ch==0 else -1
                angle+=sign*spec['PM_depth']*np.sin(modulation)
            audio[:,ch]+=spec['amplitudes'][j,ch]*gain*np.cos(angle)
    if kind=='sideband':
        audio[:,0]+=.013*np.cos(2*np.pi*q*(64+1/7)/1024+.3)
        audio[:,1]+=.017*np.cos(2*np.pi*q*(64-1/7)/1024-.2)
    if kind=='silence':audio[:]=0
    return audio


def instantaneous(spec,q):
    """True complex envelope of the64th carrier, in the declared cycle coordinate."""
    q=np.asarray(q);kind=spec['kind'];m=2*np.pi*q/(7*1024)
    z=np.broadcast_to(spec['amplitudes'][1]*np.exp(1j*spec['phases'][1]),(len(q),2)).copy()
    for ch in (0,1):
        if kind in ('common_AM','differential_AM'):
            sign=1 if kind=='common_AM' or ch==0 else -1;z[:,ch]*=1+sign*.3*np.cos(m)
        if kind in ('common_PM','relative_PM'):
            sign=1 if kind=='common_PM' or ch==0 else -1;z[:,ch]*=np.exp(1j*sign*.4*np.sin(m))
    if kind=='sideband':
        z[:,0]+=.013*np.exp(1j*(2*np.pi*q/(7*1024)+.3))
        z[:,1]+=.017*np.exp(1j*(-2*np.pi*q/(7*1024)-.2))
    if kind=='silence':z[:]=0
    return z
