"""Main V10 app recipe: existing procedural crank/catch, explicitly enabled.

This changes saved controls, not the C engine or compiled event coefficients.
Other catalogs and authored DNA retain their explicit asset-selection policy.
"""
from copy import deepcopy

def defaults(control,available_mask):
    value=deepcopy(control)
    events=value['events']
    events.update(enabled=int(bool(available_mask&6)),gain=.70,manual_sequence=0)
    events['levels']=[0.,1.25 if available_mask&2 else 0.,1. if available_mask&4 else 0.,0.,0.,0.,0.]
    return value
