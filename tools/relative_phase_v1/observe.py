"""Unweighted phase moments and amplitude-phase association, per harmonic."""
import numpy as np


def phase_budget(amplitude, phase):
    delta = phase[..., 0]-phase[..., 1]
    turn = np.exp(1j*delta)
    product = amplitude[..., 0]*amplitude[..., 1]
    phase_moment = turn.mean(axis=0)
    amplitude_product = product.mean(axis=0)
    association = (product*turn).mean(axis=0)-amplitude_product*phase_moment
    return dict(relative_phase_moment=phase_moment,
                amplitude_product=amplitude_product,
                amplitude_phase_association=association)
