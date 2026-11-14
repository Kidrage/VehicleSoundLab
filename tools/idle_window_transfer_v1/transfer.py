"""Exact finite phase-ensemble response to one and two aperture operations."""
import numpy as np
from idle75_clock_v1.row import weights
from idle75_clock_v1.forward import STARTS
from idle_window_transfer_v1.observe import CENTRES

FREQUENCIES=[.5,1.5,4.,7.]
ROWS=np.arange(10,106)


def variance(quadratures):
    x=quadratures-quadratures.mean(axis=0);return .5*(x*x).sum()/len(x)


def run(h,reference):
    response=(h/reference).real;times=np.arange(144000)/48000;rows=[];arrays={}
    for frequency in FREQUENCIES:
        q=np.column_stack((np.cos(2*np.pi*frequency*times),np.sin(2*np.pi*frequency*times)))
        windows=np.array([q[first:first+9600] for first in STARTS])
        first=np.einsum('wt,wtp->wp',response,windows)
        # First-pass116centres are50Hz; interpolate only complete support.
        second=[]
        for j in ROWS:
            t=np.arange(STARTS[j],STARTS[j]+9600)/48000;p=(t-CENTRES[0]/48000)*50
            k=np.floor(p).astype(int);w,_=weights(p-k)
            indices=k[:,None]+np.arange(-1,3);assert indices.min()>=0 and indices.max()<len(first)
            lifted=np.einsum('ti,tip->tp',w,first[indices]);second.append(response[j]@lifted)
        second=np.array(second);native=np.column_stack((np.cos(2*np.pi*frequency*CENTRES[ROWS]/48000),np.sin(2*np.pi*frequency*CENTRES[ROWS]/48000)))
        v0=variance(native);v1=variance(first[ROWS]);v2=variance(second)
        rows.append(dict(temporal_hz=frequency,native_variance=v0,first_variance=v1,second_variance=v2,
            first_power_ratio=v1/v0,second_power_ratio=v2/v0,second_over_first_power=v2/v1))
        arrays[str(frequency)]=dict(native=native,first=first,second=second)
    return rows,arrays
