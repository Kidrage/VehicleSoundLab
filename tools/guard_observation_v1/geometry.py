"""Observed candidate endpoints and spacing only; never fixture or heldout inputs."""
from copy import deepcopy
import numpy as np


def extend(previous):
    plan=deepcopy(previous)
    orders=np.asarray(plan['source_orders'],dtype=float)
    gaps=np.diff(orders)
    if len(orders)<3 or np.any(gaps<=0):
        raise ValueError('Guard geometry requires at least three ascending measured candidates')
    gap=float(gaps.min())
    step=plan['observed_order_step']
    low,high=plan['observed_order_range']
    low=min(low,float(orders[0]-gap))
    high=max(high,float(orders[-1]+gap))
    if low<=0:
        raise ValueError('Measured guard crosses the positive-frequency boundary')
    units=np.asarray([low,high])/step
    if max(abs(units-np.round(units)))>1e-10:
        raise ValueError('Measured guards do not align with the declared observation grid')
    plan['observed_order_range']=(np.round(units)*step).tolist()
    return plan,dict(previous_range=previous['observed_order_range'],range=plan['observed_order_range'],
        minimum_measured_order_gap=gap,inferred_range=[float(orders[0]),float(orders[-1])],
        candidate_source_orders_changed=False,truth_used=False,heldout_used=False,
        rule='One minimum-gap boundary sideband; never narrow original observation range')
