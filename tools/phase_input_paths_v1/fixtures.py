"""Eight deterministic positive conditional-CDF cases; no source or RNG."""
import numpy as np


def cases():
    n=np.arange(8192);t=n/1024
    product=1+.65*np.sin(2*np.pi*t/7.3)
    uniform=.5+.42*np.sin(2*np.pi*t/5.7+.3)
    knots=np.array([.2,1.,1.8])
    normal=np.array([[0.,.12,1.],[0.,.5,1.],[0.,.88,1.]])
    lo=np.array([-2.,0.]);hi=np.array([0.,2.])
    rows={
        'constant_atom':(product,uniform,knots,np.tile([0.,1.],(3,1)),np.array([.7]),np.array([.7])),
        'no_P_dependence':(product,uniform,knots,np.tile([0.,.5,1.],(3,1)),lo,hi),
        'fixed_uniform':(product,np.full(len(n),.5),knots,normal,lo,hi),
        'fixed_product':(np.ones(len(n)),uniform,knots,normal,lo,hi),
        'joint':(product,uniform,knots,normal,lo,hi),
        'repeated_atoms':(product,uniform,knots,np.array([[0.,.1,.7,1.],[0.,.3,.8,1.],[0.,.6,.9,1.]]),np.array([-2.,-2.,1.]),np.array([-2.,1.,1.])),
        'uniform_endpoints':(product,np.resize(np.array([0.,.5,1.]),len(n)),knots,normal,lo,hi),
        'P_clamped':(1+3*np.sin(2*np.pi*t/4.7),uniform,knots,normal,lo,hi),
    }
    for name,args in rows.items():
        yield name,dict(zip(('product','uniform','knots','cdf','low','high'),args))
