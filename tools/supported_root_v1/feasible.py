"""Project onto the exact finite union of nearest-peak support intervals."""
import numpy as np


def support(frequencies,roots,orders):
    frequencies=np.asarray(frequencies,dtype=float)
    roots=np.asarray(roots,dtype=float).reshape(-1)
    orders=np.asarray(orders,dtype=float)
    if not len(frequencies):
        return np.zeros((len(roots),len(orders)),dtype=bool)
    wanted=roots[:,None]*orders[None,:]
    nearest=abs(wanted[:,:,None]-frequencies[None,None,:]).argmin(axis=2)
    present=(abs(wanted-frequencies[nearest])<=np.maximum(6,.025*wanted))&(wanted>=35)&(wanted<1200)
    for column in range(len(orders)):
        if column:
            present[:,column] &= ~np.any((nearest[:,column,None]==nearest[:,:column])&present[:,:column],axis=1)
    return present


def project(proposal,frequencies,orders,root_range,minimum=3):
    frequencies=np.asarray(frequencies,dtype=float)
    orders=np.asarray(orders,dtype=float)
    lo,hi=map(float,root_range)
    if not (np.isfinite(proposal) and 0<lo<hi and np.isfinite(hi) and minimum>=1 and
            frequencies.ndim==orders.ndim==1 and len(orders) and
            np.isfinite(frequencies).all() and np.isfinite(orders).all() and (orders>0).all()):
        raise ValueError('Invalid measured-support projection arguments')
    frequencies=np.unique(frequencies)
    if np.any(frequencies<=0):
        raise ValueError('Measured peak frequencies must be positive')
    before=support(frequencies,[proposal],orders)[0]
    if lo<=proposal<=hi and before.sum()>=minimum:
        return float(proposal),dict(projected=False,delta_hz=0.,before_count=int(before.sum()),
            supported_orders=orders[before].tolist(),feasible_cells_examined=0)
    if len(frequencies)<minimum:
        raise ValueError('No distinct measured-peak support region')
    # abs(k*r-f)<=max(6,.025*k*r) is the union of the absolute and
    # relative tolerance intervals; both contain f/k, so their union is one
    # interval. Nearest-peak midpoints and35/1200 limits complete all places
    # where the original distinct-nearest support predicate can change.
    lower=np.minimum((frequencies[:,None]-6)/orders,frequencies[:,None]/(1.025*orders))
    upper=np.maximum((frequencies[:,None]+6)/orders,frequencies[:,None]/(.975*orders))
    switches=(frequencies[:-1,None]+frequencies[1:,None])/(2*orders)
    cuts=np.unique(np.clip(np.r_[lo,hi,lower.ravel(),upper.ravel(),switches.ravel(),35/orders,1200/orders],lo,hi))
    centers=(cuts[1:]+cuts[:-1])/2
    valid=support(frequencies,centers,orders).sum(axis=1)>=minimum
    low,high=cuts[:-1][valid],cuts[1:][valid]
    candidates=list(cuts[support(frequencies,cuts,orders).sum(axis=1)>=minimum])
    for left,right in zip(low,high):
        point=float(np.clip(proposal,left,right))
        center=(left+right)/2
        for _ in range(8):
            if support(frequencies,[point],orders).sum()>=minimum:
                break
            point=float(np.nextafter(point,center))
        else:
            point=float(point+(center-point)*1e-12)
        if support(frequencies,[point],orders).sum()>=minimum:
            candidates.append(point)
    if not candidates:
        raise ValueError('No distinct measured-peak support region')
    candidates=np.asarray(candidates)
    point=float(candidates[np.argmin(abs(candidates-proposal))])
    after=support(frequencies,[point],orders)[0]
    assert lo<=point<=hi and after.sum()>=minimum
    return point,dict(projected=True,delta_hz=float(point-proposal),before_count=int(before.sum()),
        supported_orders=orders[after].tolist(),feasible_cells_examined=int(len(centers)))
