"""Rank real quadrature modulation by measured residual explained energy."""
import numpy as np
from aperture_model_v1.forward import real_rows
from .model import MinorityModel


def rank(audio,time,parameters,selected,plan,variant):
    current=MinorityModel(time,plan,variant,selected)
    target=real_rows(current.aperture.apply(audio[:,0]))
    residual=target-current.prediction(parameters)
    energy=float(residual@residual)
    ranked=[]
    for index,order in enumerate(current.orders):
        if index in selected:
            continue
        candidate=MinorityModel(time,plan,variant,[index])
        probe=np.r_[parameters[:current.base_count],np.zeros(candidate.departure_count)]
        _,derivative=candidate.samples(probe,True)
        projected=real_rows(candidate.aperture.apply(derivative[:,candidate.base_count:]))
        delta=np.linalg.lstsq(projected,residual,rcond=1e-8)[0]
        explained=projected@delta
        gain=float(2*residual@explained-explained@explained)
        ranked.append(dict(index=index,order=float(order),explained_fraction=max(0.,gain)/max(energy,1e-30)))
    return sorted(ranked,key=lambda row:(-row['explained_fraction'],row['order']))
