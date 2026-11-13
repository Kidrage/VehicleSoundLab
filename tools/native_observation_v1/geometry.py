"""Fill native observation bins without changing source candidates or bandwidth."""
from copy import deepcopy
import numpy as np


def complete(previous):
    plan = deepcopy(previous)
    native = 1/plan['projection_cycles']
    original = plan['observed_order_step']
    ratio = original/native
    if ratio < 1 or abs(ratio-round(ratio)) > 1e-10:
        raise ValueError('Previous observations are not a subset of native FFT bins')
    endpoints = np.asarray(plan['observed_order_range'])/native
    if abs(endpoints-np.round(endpoints)).max() > 1e-10:
        raise ValueError('Original endpoints do not lie on native FFT bins')
    if plan['observed_order_range'][0] <= 0 or plan['observed_order_range'][1] >= plan['samples_per_cycle']/2:
        raise ValueError('Observation completion requires an interior positive-frequency band')
    plan['observed_order_step'] = native
    return plan, dict(previous_step=original, native_step=native, previous_bin_stride=int(round(ratio)),
        endpoints_unchanged=True, source_candidates_unchanged=True, window_and_hop_unchanged=True,
        regularization_added=False, zero_padding=False, truth_used=False, heldout_used=False)
