"""Main V10 defaults. Native catch-only startup is independent of events."""
from copy import deepcopy

def defaults(control,available_mask,features=0):
    value=deepcopy(control)
    events=value['events']
    if features&128:
        value.update(startup_gain=.5 if features&256 else 1.,catch_gain=0.,legacy_event_gain=0.)
        events.update(enabled=0,manual_sequence=0)
        events['levels']=[0.]*7
        return value
    events.update(enabled=int(bool(available_mask&6)),gain=.70,manual_sequence=0)
    events['levels']=[0.,1.25 if available_mask&2 else 0.,1. if available_mask&4 else 0.,0.,0.,0.,0.]
    return value
