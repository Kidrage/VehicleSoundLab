"""Declared finite phase-grid reconstruction with genuine-context guards."""
import numpy as np


def reconstruct(audio, query, radius, block=2048):
    audio, query = np.asarray(audio), np.asarray(query)
    if (audio.ndim!=2 or len(audio)<2 or np.iscomplexobj(audio) or not np.isfinite(audio).all()
            or query.ndim!=1 or not len(query) or np.iscomplexobj(query) or not np.isfinite(query).all()
            or type(radius) is not int or radius not in (32,64,128)
            or type(block) is not int or block<1):
        raise ValueError('Finite real grid, queries and declared interpolation radius required')
    offsets = np.arange(1-radius, radius+1)
    centers = np.floor(query).astype(np.int64)
    if centers.min()+offsets[0]<0 or centers.max()+offsets[-1]>=len(audio):
        raise ValueError('Genuine phase context required; no padding or extrapolation')
    answer = np.empty((len(query),audio.shape[1]))
    for first in range(0,len(query),block):
        u = query[first:first+block]
        ids = centers[first:first+block,None]+offsets[None]
        distance = u[:,None]-ids
        window = np.i0(12*np.sqrt(np.maximum(0.,1-(distance/radius)**2)))/np.i0(12.)
        weights = np.sinc(distance)*window
        weights /= weights.sum(axis=1)[:,None]
        answer[first:first+len(u)] = np.einsum('nk,nkc->nc',weights,audio[ids],optimize=True)
    return answer
