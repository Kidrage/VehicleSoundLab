"""A nonnegative Fejer partition; measured geometry only."""
import numpy as np


def basis(time,cycles,orders):
    orders=np.asarray(orders,dtype=float)
    gaps=np.diff(orders)
    if len(gaps)<2 or np.any(gaps<=0):
        raise ValueError('At least three ascending measured candidates required')
    period=2*cycles
    limit=float(gaps.min()/2)
    degree=int(np.floor(period*limit+1e-10))
    if degree<1:
        raise ValueError('Observed interval does not resolve an amplitude mode')
    controls=2*degree+1
    angle=2*np.pi*(np.asarray(time)[:,None]/period-np.arange(controls)[None,:]/controls)
    weights=np.ones_like(angle)
    for k in range(1,degree+1):
        weights+=2*(1-k/(degree+1))*np.cos(k*angle)
    weights/=controls
    if weights.min()<-1e-12 or abs(weights.sum(axis=1)-1).max()>1e-12:
        raise ValueError('Positive amplitude partition check failed')
    # Fixing one control eliminates the scale gauge while preserving positivity.
    return weights[:,1:],dict(period_coarse_cycles=float(period),degree=degree,translates=controls,
        maximum_amplitude_frequency=degree/period,measured_half_gap_limit=limit,
        partition_minimum=float(weights.min()),partition_sum_maximum_error=float(abs(weights.sum(axis=1)-1).max()),
        fixed_control=0,literal_finite_bandwidth=True,truth_used=False,heldout_used=False)
