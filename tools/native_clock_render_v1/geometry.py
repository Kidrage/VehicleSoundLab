"""One observed common stereo inverse clock; require complete real FIR support."""
import numpy as np


def dense_query(source_seconds,native_start,count,rate=48000,up=16,delay=2048):
    p=np.asarray(source_seconds)
    if (p.ndim!=1 or len(p)<2 or np.iscomplexobj(p) or not np.isfinite(p).all()
            or np.any(np.diff(p)<=0) or type(count) is not int or count<1
            or not np.isfinite(native_start) or rate!=48000 or up not in (16,32)
            or type(delay) is not int or delay!=128*up):
        raise ValueError('Observed monotonic clock and declared native grid required')
    origin=float(p[0]);relative=p-origin
    offsets=np.arange(-delay,(count-1)*up+delay+1)
    times=(native_start-origin)+offsets/(rate*up)
    if times[0]<0 or times[-1]>relative[-1]:
        raise ValueError('Actual observed phase context must include both FIR edges')
    indices=np.interp(times,relative,np.arange(len(p),dtype=float))
    return indices,origin+times,dict(first_seconds=float(origin+times[0]),last_seconds=float(origin+times[-1]),
        dense_frames=len(times),native_frames=count,rate=rate,up=up,delay=delay,
        observed_source_seconds=[float(p[0]),float(p[-1])],no_extrapolation=True)
