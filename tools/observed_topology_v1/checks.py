"""Independent analytic constant-line controls for discovery only."""
import numpy as np
from .discover import discover


def controls(geometry,settings):
    time=np.arange(geometry['cycles']*geometry['samples_per_cycle'])/geometry['samples_per_cycle']
    rows=[]
    for label,orders in [('sparse',[1.2,2.6,3.8,7.8]),('empty',[])]:
        audio=np.zeros((len(time),2))
        for index,order in enumerate(orders):
            audio[:,0]+=(.02+.003*index)*np.cos(2*np.pi*order*time+.21*index)
            audio[:,1]+=.7*(.02+.003*index)*np.cos(2*np.pi*order*time+.21*index+.4)
        inferred,evidence=discover(audio,time,geometry,settings)
        assert inferred==orders
        error=0.
        for index,order in enumerate(orders):
            column=evidence['orders'].index(order)
            error=max(error,max(abs(row['amplitudes'][column]-(.02+.003*index)) for row in evidence['intervals']))
        assert error<1e-12
        rows.append(dict(id=label,passed=True,maximum_known_amplitude_error=error,inferred=inferred))
    return dict(cases=rows,passed=True)
