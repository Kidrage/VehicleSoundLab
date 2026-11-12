"""Keep original fixtures exact and add independently moving partials."""
import numpy as np
from aperture_model_v1.fixtures import make as original


def make(case,plan):
    time,audio,truth=original(case,plan)
    orders=plan['source_orders']+plan['heldout_orders']
    independent=plan['source_orders'] if case.get('independent_all') else case.get('independent_orders',[])
    for order in independent:
        index=orders.index(order)
        amplitude=.045 if order in (2,3,5,7) else .022*(1+.15*np.cos(index*.31))
        envelope=1+.09*np.sin(2*np.pi*(.018+.0004*index)*time+.19*index) if case['amplitude'] else 1
        angle=2*np.pi*order*(time+truth)+.37*order+.013*order*order
        delta=.6*np.sin(2*np.pi*(.11+.012*index)*time)
        audio[:,0]+=amplitude*envelope*(np.cos(angle+delta)-np.cos(angle))
        right=angle+.17+.021*order
        audio[:,1]+=.82*amplitude*envelope*(np.cos(right+delta)-np.cos(right))
    return time,audio,truth
