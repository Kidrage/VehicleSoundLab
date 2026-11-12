"""Whitelist numerical geometry and discovery settings at the caller boundary."""
from copy import deepcopy

GEOMETRY_KEYS=('cycles','samples_per_cycle','base_hz','observed_order_range','observed_order_step',
    'projection_cycles','projection_hop_cycles','phase_knot_cycles','amplitude_knot_cycles',
    'phase_control_bound_cycles','amplitude_control_bound','maximum_evaluations','soft_l1_scale','rules')
DISCOVERY_KEYS=('dictionary_denominator','dictionary_order_range','minimum_relative_amplitude',
    'minimum_absolute_amplitude','maximum_dictionary_condition','support_intervals')


def numerical_inputs(base,catalog):
    return ({key:deepcopy(base[key]) for key in GEOMETRY_KEYS},
        {key:deepcopy(catalog[key]) for key in DISCOVERY_KEYS})
