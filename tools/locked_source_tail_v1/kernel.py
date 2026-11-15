"""Long Kaiser20 sinc diagnostic, with all genuine source context retained."""
import numpy as np


def reference(samples, query, radius, block=256):
    samples, query = np.asarray(samples), np.asarray(query)
    if (samples.ndim != 2 or np.iscomplexobj(samples) or not np.isfinite(samples).all()
            or query.ndim != 1 or not query.size or np.iscomplexobj(query) or not np.isfinite(query).all()
            or type(radius) is not int or radius not in (512, 1024, 2048)
            or type(block) is not int or block < 1):
        raise ValueError('Finite source, queries and declared diagnostic radius required')
    centers = np.floor(query).astype(np.int64)
    offsets = np.arange(1-radius, radius+1)
    if centers.min()+offsets[0] < 0 or centers.max()+offsets[-1] >= len(samples):
        raise ValueError('Genuine source support required; no padding or extrapolation')
    answer = np.empty((len(query), samples.shape[1]))
    for first in range(0, len(query), block):
        ids = centers[first:first+block, None]+offsets[None]
        d = query[first:first+block, None]-ids
        w = np.sinc(d)*np.i0(20*np.sqrt(np.maximum(0., 1-(d/radius)**2)))/np.i0(20.)
        w /= w.sum(axis=1)[:, None]
        answer[first:first+len(ids)] = np.einsum('ij,ijc->ic', w, samples[ids], optimize=True)
    return answer
