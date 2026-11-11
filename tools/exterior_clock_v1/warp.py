"""Shared L/R acoustic-cycle warp with a source-rate antialias budget."""
import numpy as np
from scipy import signal

RATE=48000
CYCLE=1024


def render_positions(audio,source_start,positions,cutoff):
    # Source seconds may be large; tolerate only sub-microsample subtraction
    # roundoff when a requested context lands exactly on a real sample edge.
    first=int(np.floor((positions[0]-source_start)*RATE+1e-6))-4800
    stop=int(np.ceil((positions[-1]-source_start)*RATE-1e-6))+4801
    if first<0 or stop>len(audio):
        raise ValueError('Need100ms actual source context around every position')
    taps=signal.firwin(1025,cutoff,fs=RATE,window=('kaiser',12))
    filtered=signal.fftconvolve(audio[first:stop],taps[:,None],mode='same',axes=0)
    dense=signal.resample_poly(filtered,16,1,axis=0,window=('kaiser',8.6),padtype='line')
    at=(positions-source_start-first/RATE)*RATE*16
    return np.column_stack([np.interp(at,np.arange(len(dense)),dense[:,c]) for c in (0,1)])


def warp(audio,source_start,clock_times,root_hz,start,stop,adaptive=True):
    if not(clock_times[0]<=start<stop<=clock_times[-1]):
        raise ValueError('Never extrapolate an observed clock')
    times=np.arange(round(start*RATE),round(stop*RATE)+1)/RATE
    hz=np.interp(times,clock_times,root_hz)
    if not np.isfinite(hz).all() or min(hz)<=0:
        raise ValueError('Positive finite acoustic clock required')
    phase=np.r_[0,np.cumsum((hz[1:]+hz[:-1])/(2*RATE))]
    positions=np.interp(np.arange(int(phase[-1]*CYCLE))/CYCLE,phase,times)
    cutoff=min(14000.,.38*CYCLE*float(min(hz))) if adaptive else 14000.
    result=render_positions(audio,source_start,positions,cutoff)
    return result,positions,dict(source_seconds=[start,stop],source_cutoff_hz=cutoff,
        initial_root_hz_range=[float(min(hz)),float(max(hz))],
        adaptive_source_antialias=adaptive,normalized_cycle_hz=RATE/CYCLE,
        normalized_frames=len(result),source_min_nyquist_hz=.5*CYCLE*float(min(hz)),
        processing='One common stereo inverse phase map; source FIR;16x Kaiser interpolation; no gain/compression/highpass/channel folding')


def carrier_rows(audio,order,cycles=4):
    size=CYCLE*cycles
    starts=np.arange(0,len(audio)-size+1,256)
    if len(starts)<3:
        raise ValueError('Insufficient complete windows for carrier phase')
    window=signal.windows.hann(size,sym=False)
    rows=np.array([np.fft.rfft(audio[start:start+size]*window[:,None],axis=0)[order*cycles]*
        2/window.sum()*np.exp(-2j*np.pi*order*start/CYCLE) for start in starts])
    return starts+size/2,rows


def polish(audio,source_start,normalized,positions,reference,cutoff):
    """Observe one carrier's phase, then resample original L/R once again.

    No synthesis or channel-independent phase adjustment. Reference-channel L
    only estimates a common clock correction; held-out orders validate it.
    Two edge cycles on both sides are discarded rather than extrapolated.
    """
    centers,rows=carrier_rows(normalized,reference)
    angle=np.unwrap(np.angle(rows[:,0]))
    if np.max(abs(np.diff(angle)))>np.pi*.8:
        raise ValueError('Carrier phase is not connected at the analysis hop')
    correction=(angle-angle[0])/(2*np.pi*reference)
    first,last=int(centers[0]),int(centers[-1])
    indices=np.arange(first,last+1)
    new_phase=indices/CYCLE+np.interp(indices,centers,correction)
    if np.min(np.diff(new_phase))<=0:
        raise ValueError('Corrected coordinate must stay monotonic')
    sample_phase=np.arange(int(np.ceil(new_phase[0]*CYCLE)),int(np.floor(new_phase[-1]*CYCLE)))/CYCLE
    at=np.interp(sample_phase,new_phase,indices)
    source_positions=np.interp(at,np.arange(len(positions)),positions)
    inferred=1/(CYCLE*np.diff(source_positions))
    final_cutoff=min(cutoff,.38*CYCLE*float(min(inferred)))
    result=render_positions(audio,source_start,source_positions,final_cutoff)
    return result,source_positions,dict(reference_order=reference,
        reference_channel='L observation; same coordinate applied to both original channels',
        fitted_phase_range_radians=[float(angle.min()),float(angle.max())],
        maximum_observed_phase_step_radians=float(max(abs(np.diff(angle)))),
        source_cutoff_hz=final_cutoff,source_seconds=[float(source_positions[0]),float(source_positions[-1])],
        inferred_root_hz_range=[float(inferred.min()),float(inferred.max())],
        root_hz_median=float(np.median(inferred)),normalized_frames=len(result),
        edge_policy='Discard both unsupported two-cycle margins; never extrapolate phase correction',
        warning='Fitted reference coherence is not validation; inspect separate carrier orders and known controls')
