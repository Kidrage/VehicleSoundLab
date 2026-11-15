"""Continuous full-order OSC evaluation at arbitrary phase coordinates."""
import numpy as np


def evaluate(nodes,positions,orders,query,block=512):
    nodes,positions,orders,query=map(np.asarray,(nodes,positions,orders,query))
    if (positions.ndim!=1 or len(positions)<2 or np.iscomplexobj(positions)
            or not np.isfinite(positions).all() or np.any(np.diff(positions)<=0)
            or orders.ndim!=1 or not len(orders) or np.iscomplexobj(orders)
            or not np.isfinite(orders).all() or np.any(orders!=orders.astype(int))
            or np.any((orders<1)|(orders>511)) or len(np.unique(orders))!=len(orders)
            or nodes.shape!=(len(positions),len(orders),2) or not np.isfinite(nodes).all()
            or query.ndim!=1 or not len(query) or np.iscomplexobj(query) or not np.isfinite(query).all()
            or np.any(query<positions[0]) or np.any(query>positions[-1])
            or type(block) is not int or block<1):
        raise ValueError('Finite full stereo model, strictly increasing nodes and supported phase queries required')
    out=np.empty((len(query),2))
    for first in range(0,len(query),block):
        u=query[first:first+block]
        slot=np.clip(np.searchsorted(positions,u,side='right')-1,0,len(positions)-2)
        weight=(u-positions[slot])/(positions[slot+1]-positions[slot])
        coefficients=nodes[slot]*(1-weight[:,None,None])+nodes[slot+1]*weight[:,None,None]
        angle=2*np.pi*((u[:,None]%1024)*orders[None,:]%1024)/1024
        out[first:first+len(u)]=np.einsum('nhc,nh->nc',coefficients,np.exp(1j*angle),optimize=True).real
    return out
