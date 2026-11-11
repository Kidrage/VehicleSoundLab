"""Raw stereo band powers in an explicit moving acoustic coordinate."""
import numpy as np
from shift_evidence_v1.spectrum import observe


def measure(audio, source_start, times, roots, seconds, scale=1):
    data = observe(audio, source_start, 80, clock=(times, roots*5*scale))
    keep = ((data['seconds'] >= seconds[0]+.04) &
            (data['seconds'] <= seconds[1]-.04))
    if int(keep.sum()) < 20:
        raise ValueError('Need at least20 actual windows inside the fixed interval')
    power = data['relative_power_LR'][:, :, keep].mean(axis=2)
    cross = data['relative_cross_LR'][:, keep].mean(axis=1)
    correlation = cross/np.sqrt(np.maximum(power[0]*power[1], 1e-60))
    return dict(windows=int(keep.sum()), power_LR=power.tolist(),
                shape_relative_mid_db_LR=(10*np.log10(power[:, 3:5]/power[:, 2, None])).T.tolist(),
                complex_correlation=[[float(z.real), float(z.imag)] for z in correlation])
