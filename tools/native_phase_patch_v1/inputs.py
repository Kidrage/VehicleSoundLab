"""Observed full native inventories and their neighbour-derived rate initializer."""
import numpy as np
from accel_ridges_v1.observe import inventory
from accel_low_fit_v1.observe import initial_graphs


def observe(audio,frames,ridge_plan):
    inventories,guides=[],[]
    for start in range(0,len(audio),frames):
        tile=audio[start:start+frames]
        lo=inventory(tile,dict(ridge_plan,inventory_hz=[30,200]))
        hi=inventory(tile,ridge_plan)
        inv=dict(bin=lo['bin']+hi['bin'],hz=lo['hz']+hi['hz'])
        power=lo['power_LR']+hi['power_LR']
        peak=int(np.argmax(np.sum(power,axis=1)))
        inventories.append(inv)
        guides.append(dict(native_inventory_index=peak,observed_hz=inv['hz'][peak]))
    ratios=[v['observed_hz']/guides[0]['observed_hz'] for v in guides]
    return dict(inventories=inventories,guides=guides,ratios=ratios,
        initial=initial_graphs(inventories,ratios,ridge_plan))
