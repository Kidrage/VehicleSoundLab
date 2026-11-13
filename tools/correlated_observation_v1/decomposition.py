"""Known-fixture decomposition, isolated from observed estimation interfaces."""
import numpy as np


def analytic_components(time, source_orders, heldout_orders, case):
    epsilon = .055*np.exp(-((time-18)/1.3)**2)-.035*np.exp(-((time-21)/.9)**2)+.012*np.sin(2*np.pi*.077*time)
    epsilon -= epsilon[0]
    source = np.zeros((len(time), 2))
    omitted = np.zeros_like(source)
    for index, order in enumerate(source_orders+heldout_orders):
        amplitude = .045 if order in (2, 3, 5, 7) else .022*(1+.15*np.cos(index*.31))
        envelope = 1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index)
        angle = 2*np.pi*order*(time+epsilon)+.37*order+.013*order*order
        values = np.column_stack((amplitude*envelope*np.cos(angle),
            .82*amplitude*envelope*np.cos(angle+.17+.021*order)))
        if index < len(source_orders):
            source += values
        else:
            omitted += values
    noise = case['noise']*np.random.default_rng(910284).normal(size=source.shape)
    gain = case['gain']
    return gain*source, gain*omitted, gain*noise
