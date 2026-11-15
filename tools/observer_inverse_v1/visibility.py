"""Coverage of the original complete, unpadded finite-Hann observation rows."""
import numpy as np


def coverage(frames):
    starts=np.arange(0,frames-4096+1,256)
    window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    squared=np.zeros(frames)
    for start in starts:
        squared[start:start+4096]+=window**2
    return dict(starts=starts,squared_window_coverage=squared,
        unobserved=np.flatnonzero(squared==0),trailing_unobserved=frames-int(starts[-1]+4096))
