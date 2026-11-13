"""Declared harmonic rise/fall fixtures without added periodic modulation."""
import numpy as np


def fixtures(rate=48000):
    t=np.arange(rate)/rate-.5
    f=np.array([75.2,112.8,188.,82.3]);amp=np.array([.5,.4,.3,.18]);phase=np.array([.2,.5,.8,.1])
    for name,slope in [('inside_flat_box',.3),('positive_crossing',.6),('negative_crossing',-.6)]:
        q=np.array([2*slope,3*slope,5*slope,-.2])
        x=(amp*np.cos(2*np.pi*(t[:,None]*f+.5*t[:,None]**2*q)+phase)).sum(axis=1)
        yield dict(id=name,audio=x,frequency=f,chirp=q,central=amp*np.exp(1j*phase),labels=[75,113,188,82],root_slope=slope)
