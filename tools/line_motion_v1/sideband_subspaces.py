"""Equal-dimensional conditional amplitude/quadrature residual spaces."""
import numpy as np


def matrices(frequency,chirp,central,time,rotation=0.):
    phase=2*np.pi*(time[:,None]*frequency+.5*time[:,None]**2*chirp)+rotation
    z=np.exp(1j*phase);v=z*(central*np.exp(-1j*rotation))
    base=np.column_stack((z.real,z.imag,np.ones(len(time))))
    c=np.cos(2*np.pi*3*time[:,None]);s=np.sin(2*np.pi*3*time[:,None])
    amplitude=np.column_stack((v.real*c,v.real*s));quadrature=np.column_stack((-v.imag*c,-v.imag*s))
    return dict(base=base,amplitude=np.column_stack((base,amplitude)),quadrature=np.column_stack((base,quadrature)),
        joint=np.column_stack((base,amplitude,quadrature)))


def observe(audio,frequency,chirp,central,time,rotation=0.):
    weight=np.cos(np.pi*time)/np.sqrt(len(time));waves={};fits={}
    for name,matrix in matrices(frequency,chirp,central,time,rotation).items():
        coefficient,_,rank,singular=np.linalg.lstsq(weight[:,None]*matrix,weight*audio,rcond=None)
        fitted=matrix@coefficient;residual=fitted-audio;gradient=matrix.T@(weight**2*residual)
        waves[name]=fitted;fits[name]=dict(coefficients=coefficient.tolist(),rank=int(rank),columns=matrix.shape[1],
            singular_values=singular.tolist(),condition=float(singular[0]/singular[-1]),
            cost=float(.5*np.dot(weight**2,residual**2)),gradient_infinity=float(abs(gradient).max()))
    return waves,fits
