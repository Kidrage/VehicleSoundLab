"""Fixture truth is isolated from the discovery and fit interfaces."""
from copy import deepcopy
from minority_phase_v1.fixtures import make as original


def make(case,base):
    plan=deepcopy(base)
    if 'fixture_orders' in case:
        plan['source_orders']=case['fixture_orders']
    time,audio,truth=original(case,plan)
    audio*=case.get('gain',1)
    return time,audio,truth,plan
