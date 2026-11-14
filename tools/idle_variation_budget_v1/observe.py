"""One unchanged oscillator observation basis shared by any number of buses."""
import numpy as np

SELECTED=np.array([1,2,4])
STARTS=np.arange(12000,122401,960)


def observe(buses,frequencies,phasors):
    buses=np.asarray(buses);assert buses.shape[0]==144000 and buses.ndim==2
    t=np.arange(len(buses))/48000
    z=np.exp(2j*np.pi*t[:,None]*np.asarray(frequencies));z[:,SELECTED]=phasors
    A=np.column_stack((z.real,z.imag,np.ones(len(z))))
    w=.5-.5*np.cos(2*np.pi*np.arange(9600)/9600);values=[];conditions=[]
    for first in STARTS:
        slab=A[first:first+9600];gram=slab.T@(slab*w[:,None]);eig=np.linalg.eigvalsh(gram)
        if eig.min()<=np.finfo(float).eps*27*eig.max():raise ValueError('Unresolved joint basis')
        beta=np.linalg.solve(gram,slab.T@(buses[first:first+9600]*w[:,None]))
        values.append((beta[:13]-1j*beta[13:26]).T)
        conditions.append(np.sqrt(eig.max()/eig.min()))
    return np.array(values),np.array(conditions)
