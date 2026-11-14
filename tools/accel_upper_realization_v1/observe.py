"""Per-passage native observations, keeping theoretical and finite power denominators separate."""
import numpy as np
from accel_upper_joint_v1.moments import energy_partition
from accel_upper_carrier_v1.spectral import measure


def observe_block(audio,tile,theoretical_power,size=480):
    x=np.asarray(audio);tile=np.asarray(tile);P=np.asarray(theoretical_power)
    if x.shape!=(len(tile)*size,4) or P.shape!=(4,) or np.any(P<=0):raise ValueError('Exact full native windows and four positive model powers required')
    power=np.mean(x.reshape(len(tile),size,4)**2,axis=1);part=energy_partition(power,tile);C,starts=measure(x)
    return dict(power=power,power_mean=part['mean'],signed_lagged=part['lagged'],
        theoretical_normalized=part['lagged']/np.outer(P,P),measured_normalized=part['normalized_lagged'],
        lag_counts=part['lag_counts'],spectrum=C,starts=starts)


def observe_run(audio,tile,theoretical_power,blocks=8):
    frames=len(tile)*480
    if len(audio)!=blocks*frames:raise ValueError('Unexpected continuous realization duration')
    rows=[observe_block(audio[b*frames:(b+1)*frames],tile,theoretical_power) for b in range(blocks)]
    result={key:np.stack([row[key] for row in rows]) for key in ['power','power_mean','signed_lagged','theoretical_normalized','measured_normalized']}
    result.update(pooled_spectrum=sum(row['spectrum'] for row in rows)/blocks,lag_counts=rows[0]['lag_counts'],starts=rows[0]['starts'])
    return result
