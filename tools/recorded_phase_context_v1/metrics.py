"""Unfitted complete-window carrier checks, with genuine outer window support."""
import numpy as np
from exterior_clock_v1.warp import carrier_rows, CYCLE


def heldout(arrays):
    result = {}
    first = arrays['sample_indices'][2048]
    last = arrays['sample_indices'][-2049]
    for order in (3,7):
        centers, rows = carrier_rows(arrays['validation_audio'], order)
        centers += arrays['validation_indices'][0]
        groups = dict(whole=np.ones(len(centers),dtype=bool),
                      before=centers<first, target=(centers>=first)&(centers<=last),
                      after=centers>last)
        result[str(order)] = {}
        for name,mask in groups.items():
            if not np.any(mask):raise ValueError('Complete outer heldout windows missing')
            z=rows[mask]
            result[str(order)][name] = dict(windows=int(mask.sum()),
                coherence=(abs(z.mean(axis=0))/np.maximum(np.mean(abs(z),axis=0),1e-300)).tolist(),
                mean_amplitude=np.mean(abs(z),axis=0).tolist())
    return result
