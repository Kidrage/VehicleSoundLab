"""Native positive conditional means through the unchanged complex OSC observer."""
import numpy as np
from joint_osc_forward_v1.projection import compile_response,apply,derivative

SELECTED=np.array([1,2,4])
ACTIVE=np.array([0,1])


def features(z):
    w=np.column_stack((z[:,2]*z[:,1].conj()*z[:,0].conj(),z[:,0]**3*z[:,1].conj()**2))
    return np.column_stack((w.real,w.imag))


def design(frequencies,z):
    t=np.arange(len(z))/48000
    c=np.exp(2j*np.pi*t[:,None]*np.asarray(frequencies));c[:,SELECTED]=z
    return np.column_stack((c.real,c.imag,np.ones(len(z))))


def prepare(frequencies,z,beta,center=None):
    A=design(frequencies,z);c=beta[:13]-1j*beta[13:26]
    cosine=np.real(z*c[SELECTED]);base=A@beta-cosine.sum(axis=1)
    x=features(z)
    if center is None:center=x[12000:-12000].mean(axis=0)
    x=x-np.asarray(center)
    spec=dict(frequencies=np.asarray(frequencies),amplitude=np.ones(13))
    cache=compile_response(spec,z,cosine,base)
    return dict(x=x,center=np.asarray(center),cache=cache,base=base,cosine=cosine,
                coefficients=c,frequencies=np.asarray(frequencies))


def gains(parameters,x):
    p=np.asarray(parameters).reshape(2,5)
    return np.column_stack((np.exp(p[:,0]+x@p[:,1:].T),np.ones(len(x))))


def response(prepared,parameters,jacobian=False):
    x=prepared['x'];g=gains(parameters,x);value=apply(prepared['cache'],g)
    if not jacobian:return value
    innovation=np.column_stack((np.ones(len(x)),x))
    dg=np.zeros((10,len(x),3))
    for mode in range(2):dg[mode*5:mode*5+5,:,mode]=(g[:,mode,None]*innovation).T
    jac=derivative(prepared['cache'],dg)
    return value,np.moveaxis(jac,0,-1)


def waveform(prepared,parameters):
    return prepared['base']+np.sum(prepared['cosine']*gains(parameters,prepared['x']),axis=1)


def global_bounds(parameters,center):
    p=np.asarray(parameters).reshape(2,5);center=np.asarray(center)
    low=p[:,0]-p[:,1:]@center-np.abs(p[:,1:]).sum(axis=1)
    high=p[:,0]-p[:,1:]@center+np.abs(p[:,1:]).sum(axis=1)
    return np.exp(np.column_stack((low,high)))
