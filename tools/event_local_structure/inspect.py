"""Compose independent resolution/hop observations without inventing peak paths."""
import numpy as np
from .spectrum import observe,inventories,RATE
from .links import links,summarize


def inspect(audio,frames,hop):
    observed=observe(audio,frames,hop)
    rows=inventories(observed)
    df=RATE/frames
    connections=links(rows,df,frames/RATE)
    result=dict(window_frames=frames,hop_frames=hop,window_seconds=frames/RATE,
        frequency_bin_hz=df,windows=len(rows),inventories=rows,links=connections,
        summaries=summarize(rows,connections,df),
        native_fullband_mean_power=float(observed['power'].sum(axis=1).mean()),
        physical_identity_or_RPM=False,tracks_interpolated=False)
    return result,observed
