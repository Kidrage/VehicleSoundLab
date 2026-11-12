"""Four-cycle slow phase observation with supported margins and no extrapolation."""
import numpy as np
from scipy import signal
from scipy.interpolate import PchipInterpolator
from phase_clock_v1.projection import carrier_rows
from exterior_clock_v1.warp import CYCLE,render_positions

def polish(audio,source_start,normalized,positions,reference,cutoff):
    centers,rows,quality=carrier_rows(normalized,reference)
    if not quality['supported'].all():
        raise ValueError('Reference below -30dB support gate')
    angle=np.unwrap(np.angle(rows[:,0]))
    if np.max(abs(np.diff(angle)))>np.pi*.8:
        raise ValueError('Reference phase not locally connected')
    # 17 quarter-cycle samples span four cycles. This deliberately estimates
    # a slow coordinate, not every phase fluctuation of a mixed recording.
    span=17
    if len(centers)<span+2:
        raise ValueError('Insufficient independent supported slow-phase margins')
    correction=signal.savgol_filter(angle,span,2)/(2*np.pi*reference)
    edge=span//2
    centers=centers[edge:-edge];correction=correction[edge:-edge]
    phase=centers/CYCLE+correction-correction[0]
    if np.min(np.diff(phase))<=0:
        raise ValueError('Nonmonotonic slow coordinate')
    at_phase=np.arange(int(np.ceil(phase[0]*CYCLE)),int(np.floor(phase[-1]*CYCLE)))/CYCLE
    index=PchipInterpolator(phase,centers,extrapolate=False)(at_phase)
    where=np.interp(index,np.arange(len(positions)),positions)
    inferred=1/(CYCLE*np.diff(where));final_cutoff=min(cutoff,.38*CYCLE*float(min(inferred)))
    if not np.isfinite(inferred).all() or min(inferred)<=0:
        raise ValueError('Invalid inverse slow clock')
    result=render_positions(audio,source_start,where,final_cutoff)
    return result,where,dict(reference=reference,span_normalized_cycles=4,
        source_seconds=[float(where[0]),float(where[-1])],root_hz_range=[float(min(inferred)),float(max(inferred))],
        source_cutoff_hz=final_cutoff,edge_policy='discard raw one-cycle and smoothing two-cycle margins per side',
        meaning='Offline slow acoustic coordinate only; not instantaneous crank speed or a runtime FM source')
