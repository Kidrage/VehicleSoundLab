"""Common physical-time lowpass and aligned decimation; never pad source audio."""
import numpy as np
from scipy import signal
from .geometry import dense_query
from .basis import evaluate


def taps(up=16):
    if up not in (16,32):raise ValueError('Declared16x/32x diagnostic realization required')
    return signal.firwin(256*up+1,22000,fs=48000*up,window=('kaiser',12),scale=True)


def render(nodes,positions,orders,source_seconds,native_start,count,*,up=16):
    if len(source_seconds)!=positions[-1]+1 or positions[0]!=0:
        raise ValueError('Exact full model endpoint and source coordinate identity required')
    kernel=taps(up);delay=(len(kernel)-1)//2
    query,times,geometry=dense_query(source_seconds,native_start,count,up=up,delay=delay)
    max_root=float(1/(1024*np.min(np.diff(source_seconds))))
    if max_root*np.max(orders)>.4*48000*up:
        raise ValueError('Source carrier exceeds declared dense sampling budget')
    wave=evaluate(nodes,positions,orders,query)
    filtered=signal.fftconvolve(wave,kernel[:,None],mode='valid',axes=0)
    output=filtered[::up]
    assert output.shape==(count,2)
    return dict(query=query,dense_times=times,dense_wave=wave,filtered_dense=filtered,
        native=output,taps=kernel),dict(geometry,max_observed_root_hz=max_root,
            no_order_or_node_reduction=True,common_LR_clock_and_filter=True,
            finite_oversampling_not_universal_alias_free_proof=True)
