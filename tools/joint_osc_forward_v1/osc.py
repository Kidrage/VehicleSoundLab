"""Known oscillator fixture and positive joint AM mapping, separate from profiles."""
import numpy as np

SELECTED=np.array([1,2,4])


def specification():
    frequencies=np.array([37.19,75.,112.5,150.12,187.5,225.43,262.77,284.61,299.84,359.43,375.16,472.63,486.93])
    amplitude=np.array([.016,.08,.075,.0105,.039,.0095,.0104,.0136,.0142,.003,.0028,.0044,.0021])
    relations=np.array([[-1.,-1.,1.],[3.,-2.,0.]])
    right=relations.T@np.linalg.inv(relations@relations.T)
    phase=np.zeros((13,5));phase[SELECTED,:2]=right*np.array([.18,.22])
    return dict(frequencies=frequencies,amplitude=amplitude,initial=np.linspace(-.9,.7,13),phase_map=phase,
        relations=relations,selected=SELECTED,log_sigma=np.array([.12,.10,.09]))


def gain_matrix(parameters,spec,enabled=True):
    r=np.asarray(parameters)
    if np.any(abs(r)>=1):raise ValueError('Strictly interior correlation parameters required')
    a=np.zeros((3,5));derivative=np.zeros((2,3,5))
    if enabled:
        s=spec['log_sigma'];a[0,[0,2]]=s[0]*np.array([r[0],np.sqrt(1-r[0]**2)])
        a[1,[1,3]]=s[1]*np.array([r[1],np.sqrt(1-r[1]**2)]);a[2,4]=s[2]
        derivative[0,0,[0,2]]=s[0]*np.array([1.,-r[0]/np.sqrt(1-r[0]**2)])
        derivative[1,1,[1,3]]=s[1]*np.array([1.,-r[1]/np.sqrt(1-r[1]**2)])
    return a,derivative


def gains(latent,covariance,parameters,spec,enabled=True):
    a,derivative=gain_matrix(parameters,spec,enabled)
    variance=np.einsum('mi,ij,mj->m',a,covariance,a)
    log=latent@a.T-variance
    g=np.exp(log);jacobian=[]
    for d in derivative:
        dv=2*np.einsum('mi,ij,mj->m',d,covariance,a)
        jacobian.append(g*(latent@d.T-dv))
    return g,np.array(jacobian),log,a


def carriers(spec,latent,rate=48000):
    t=np.arange(len(latent))/rate
    deterministic=2*np.pi*t[:,None]*spec['frequencies']+spec['initial']
    theta=deterministic+latent@spec['phase_map'].T
    real=np.cos(theta);mask=np.ones(len(spec['amplitude']),bool);mask[SELECTED]=False
    base=real[:,mask]@spec['amplitude'][mask]
    return deterministic,np.exp(1j*theta[:,SELECTED]),real[:,SELECTED],base


def waveform(spec,cosine,base,gain):
    return base+np.sum(cosine*gain*spec['amplitude'][SELECTED],axis=1)
