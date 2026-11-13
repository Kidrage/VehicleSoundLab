"""Self-consistent local derivative moment; retain every unresolved bracket."""
import numpy as np
from scipy.optimize import brentq
from .moments import observe


def centered(audio,rate,nominal):
    initial=observe(audio,rate,nominal)
    frequency=initial['frequency_Hz'].copy()
    solved=np.zeros_like(frequency,dtype=bool)
    residual=np.zeros_like(frequency)
    endpoints=np.zeros((*frequency.shape,2))
    iterations=np.zeros_like(frequency,dtype=int)
    time=np.arange(rate)/rate
    w=np.sin(np.pi*time)**2
    dw=np.pi*np.sin(2*np.pi*time)
    for line,f in enumerate(nominal):
        for channel in range(2):
            x=audio[:,channel]
            def offset(carrier):
                kernel=np.exp(-2j*np.pi*carrier*time)
                c=np.dot(kernel,w*x);d=np.dot(kernel,dw*x)
                return float(-np.imag(d/c)/(2*np.pi))
            a,b=f-.5,f+.5
            left,right=offset(a),offset(b)
            endpoints[line,channel]=[left,right]
            if np.isfinite(left) and np.isfinite(right) and left*right<=0:
                root,info=brentq(offset,a,b,xtol=1e-10,maxiter=100,full_output=True)
                if info.converged:
                    frequency[line,channel]=root;solved[line,channel]=True
                    residual[line,channel]=offset(root);iterations[line,channel]=info.iterations
    return dict(**{k:v for k,v in initial.items() if k!='frequency_Hz'},frequency_Hz=frequency,
        initial_frequency_Hz=initial['frequency_Hz'],root_resolved=solved,
        root_residual_Hz=residual,endpoint_offsets_Hz=endpoints,root_iterations=iterations)
