"""Finite interval compatibility, retaining all extra lines and subharmonic ambiguity."""
import math


def compatible(anchors,orders,extras,half_width):
    low=max((value-half_width)/order for value,order in zip(anchors,orders))
    high=min((value+half_width)/order for value,order in zip(anchors,orders))
    if low>high or low<=0:
        return dict(anchor_interval_Hz=None,branches=[],compatible=False)
    anchor=[float(low),float(high)]
    branches=[dict(base_interval_Hz=anchor,extra_orders=[])]
    for value in extras:
        following=[]
        for branch in branches:
            low,high=branch['base_interval_Hz']
            first=max(1,math.ceil((value-half_width)/high))
            last=math.floor((value+half_width)/low)
            for order in range(first,last+1):
                left=max(low,(value-half_width)/order)
                right=min(high,(value+half_width)/order)
                if left<=right:
                    following.append(dict(base_interval_Hz=[float(left),float(right)],
                        extra_orders=branch['extra_orders']+[order]))
        branches=following
    return dict(anchor_interval_Hz=anchor,branches=branches,compatible=bool(branches))
