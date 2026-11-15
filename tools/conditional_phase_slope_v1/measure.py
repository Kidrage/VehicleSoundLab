"""CDF slope bounds and deterministic path probes, not engine time constants."""
import numpy as np
from conditional_phase_v1.decoder import decode


def measure(cdf,knots,low,high):
    probability=np.diff(cdf,axis=1);width=high-low
    if probability.min()<=0:raise ValueError('Conditional cells must be strictly positive')
    uniform=float(np.max(width[None,:]/probability))
    if len(knots)>1:
        dc=np.diff(cdf,axis=0)/np.diff(knots)[:,None]
        cdf_gradient=float(abs(dc).max())
        product=float(np.max(width[None,:]/np.minimum(probability[:-1],probability[1:])*
                  np.maximum(abs(dc[:,:-1]),abs(dc[:,1:]))))
    else:cdf_gradient=product=0.
    return dict(inverse_uniform_slope_bound=uniform,cdf_product_gradient=cdf_gradient,
                inverse_product_slope_bound=product,minimum_cell_probability=float(probability.min()))


def probes(cdf,knots,low,high):
    # Same two unitless, fixed paths in every model; neither is a measured RPM
    # trajectory, observed stochastic time law, or audible waveform.
    t=np.linspace(0,1,1025)
    product=knots[0]+(knots[-1]-knots[0])*(.5-.45*np.cos(2*np.pi*t))
    uniform=.5+.45*np.sin(4*np.pi*t+.31)
    values=decode(product,uniform,knots,cdf,low,high)
    return dict(product=product,uniform=uniform,phase=values,
                maximum_step_radians=float(abs(np.diff(values)).max()),
                step_RMS_radians=float(np.sqrt(np.mean(np.diff(values)**2))))
