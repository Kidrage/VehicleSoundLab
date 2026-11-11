"""Offline common-channel pitch compensation in an observed-ridge coordinate.

The caller supplies a supported frequency path; it need not be a fundamental
or physical engine order. No recovered audio is used by the C synthesizer.
"""
import numpy as np
from scipy import signal


def compensate(audio,rate,track_seconds,track_hz,origin_seconds=0,upsampling=16):
    x=np.asarray(audio);t=np.asarray(track_seconds);f=np.asarray(track_hz)
    if x.ndim!=2 or x.shape[1]!=2 or len(t)<3 or t.shape!=f.shape or not np.isfinite(x).all() or not np.isfinite(t).all() or not np.isfinite(f).all():
        raise ValueError('Finite stereo and supported path required')
    if np.any(np.diff(t)<=0) or np.min(f)<=0 or upsampling<4:raise ValueError('Invalid monotonic time/path frequency')
    first=int(np.ceil((t[0]-origin_seconds)*rate));last=int(np.floor((t[-1]-origin_seconds)*rate))
    if not 0<=first<last<len(x):raise ValueError('Path outside supplied audio')
    source_seconds=origin_seconds+np.arange(first,last+1)/rate
    sampled_frequency=np.interp(source_seconds,t,f)
    reference=.98*float(np.min(sampled_frequency))
    # u integrates relative observed cycles. reference <= every f ensures
    # dt/du <= 1, so no input frequency is shifted upward toward Nyquist.
    u=np.r_[0,np.cumsum((sampled_frequency[:-1]+sampled_frequency[1:])/(2*rate*reference))]
    out_seconds=np.arange(int(np.floor(u[-1]*rate))+1)/rate
    inverse=np.interp(out_seconds,u,source_seconds)
    guard=round(.04*rate);a=max(0,first-guard);b=min(len(x),last+guard+1)
    dense=signal.resample_poly(x[a:b],upsampling,1,axis=0,window=('kaiser',8.6),padtype='line')
    index=(inverse-origin_seconds-a/rate)*rate*upsampling
    y=np.column_stack([np.interp(index,np.arange(len(dense)),dense[:,c]) for c in range(2)])
    metadata=dict(reference_hz=reference,input_sample_seconds=[float(source_seconds[0]),float(source_seconds[-1])],
        input_ridge_hz=[float(sampled_frequency[0]),float(sampled_frequency[-1])],
        input_frames=last-first+1,output_frames=len(y),output_seconds=len(y)/rate,
        min_input_time_step_per_output_time=float(reference/np.max(sampled_frequency)),
        max_input_time_step_per_output_time=float(reference/np.min(sampled_frequency)),
        interpolation=dict(upsampling=upsampling,filter='scipy resample_poly default 20*up+1-tap Kaiser beta 8.6, then linear interpolation',guard_seconds=.04),
        meaning='Normalized time based on one observed ridge; not crank/RPM, source separation, raw-time dynamics or an identified physical order.',
        channel_policy='One inverse-time map and identical resampling filter for L/R; no waveform channel sum')
    return y,metadata,dict(normalized_seconds=out_seconds,source_seconds=inverse)
