"""Extend geometry, retaining the target's EXACT shared weights and scales."""
import copy
import numpy as np
from observer_complete_v1.frame import CompleteHann
from observer_supported_v1.metric import SupportedMetric


def extend(reference, frames, left=2048, right=2048):
    if type(reference) is not SupportedMetric:
        raise ValueError('Original SupportedMetric required')
    if any(type(x) is not int for x in (frames,left,right)) or left!=2048 or right!=2048:
        raise ValueError('Declared two-cycle2048 context each side required')
    if frames != reference.frame.frames+left+right:
        raise ValueError('Context geometry differs from original target')
    # Keep the public concrete contract so the already-qualified shared
    # geometry accepts it. No source/channel statistics are re-estimated.
    result = copy.copy(reference)
    result.frame = CompleteHann(frames,reference.frame.channels)
    result.keep = (result.frame.starts>=0)&(result.frame.starts+4096<=frames)
    result.full_rows = int(result.keep.sum())
    result.shape = (result.full_rows,2049,result.frame.channels)
    for name in ('weights','bands','band_power','floor_active'):
        setattr(result,name,getattr(reference,name).copy())
    coverage = np.zeros(frames)
    for first,last,offset in (s for s,k in zip(result.frame.support,result.keep) if k):
        coverage[first:last] += result.frame.window[offset:offset+last-first]**2
    result.time_coverage = result.amplitude_scale**2*coverage/result.frame.coverage
    old_starts = reference.frame.starts[reference.keep]
    new_starts = result.frame.starts[result.keep]
    slots = np.searchsorted(new_starts,old_starts+left)
    if not np.array_equal(new_starts[slots],old_starts+left):
        raise ArithmeticError('Original fully supported windows were not retained')
    if not np.array_equal(result.frame.coverage[left:frames-right],reference.frame.coverage):
        raise ArithmeticError('Original finite-frame normalization changed')
    result.target_window_slots = slots
    result.target_slice = slice(left,frames-right)
    return result


def nodes(original, frames):
    original = np.asarray(original)
    if (original.ndim!=1 or len(original)<3 or not np.isfinite(original).all()
            or np.any(np.diff(original)<=0) or original[0]!=0
            or original[-1]!=frames-4097):
        raise ValueError('Exact original nonuniform target nodes required')
    result = np.r_[np.arange(-2048,0,256),original,original[-1]+np.arange(256,2049,256)]+2048
    if result[0]!=0 or result[-1]!=frames-1 or not np.array_equal(result[8:-8]-2048,original):
        raise ArithmeticError('Original node geometry changed')
    return result
