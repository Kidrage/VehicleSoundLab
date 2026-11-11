"""First-order window-moment correction with four-cycle frequency selectivity."""
import numpy as np
from scipy.signal import savgol_filter
from exterior_clock_v1.warp import CYCLE, render_positions
from .projection import carrier_rows, diagnostics, independent_agreement


def polish(audio, source_start, normalized, positions, reference, cutoff):
    centers, rows, quality=carrier_rows(normalized,reference,cycles=4)
    if len(centers)<9 or not quality['supported'].all():
        raise ValueError('Need9 supported four-cycle phase observations')
    angle=np.unwrap(np.angle(rows[:,0]))
    if max(abs(np.diff(angle)))>np.pi*.8:raise ValueError('Four-cycle carrier phase is not connected')
    phase=(angle-angle[0])/(2*np.pi*reference)
    # Hann window second central moment in root cycles. For slowly changing
    # phase, observation ~= phase + variance/2 * phase''. This inverse is only
    # first-order and must be tested on independent rapid/changing-amplitude data.
    variance=4**2*(1/12-1/(2*np.pi**2))
    curvature=savgol_filter(phase,9,3,deriv=2,delta=.25,mode='interp')
    corrected=phase-.5*variance*curvature
    corrected-=corrected[0]
    indices=np.arange(int(centers[0]),int(centers[-1])+1)
    observed=indices/CYCLE+np.interp(indices,centers,corrected)
    if min(np.diff(observed))<=0:raise ValueError('Debiased phase is not monotonic')
    grid=np.arange(int(np.ceil(observed[0]*CYCLE)),int(np.floor(observed[-1]*CYCLE)))/CYCLE
    at=np.interp(grid,observed,indices);where=np.interp(at,np.arange(len(positions)),positions)
    roots=1/(CYCLE*np.diff(where));final_cutoff=min(cutoff,.38*CYCLE*float(min(roots)))
    result=render_positions(audio,source_start,where,final_cutoff)
    measured=diagnostics(result,reference)
    evidence=dict(reference_order=reference,projection_cycles=4,debias_moment_cycles2=float(variance),
        derivative_rule='9 observations, cubic Savitzky-Golay second derivative; first-order moment inverse',
        reference_channel='L; same inverse coordinate applies to original L/R',
        maximum_moment_correction_cycles=float(max(abs(.5*variance*curvature))),
        source_cutoff_hz=final_cutoff,source_seconds=[float(where[0]),float(where[-1])],
        inferred_root_hz_range=[float(min(roots)),float(max(roots))],
        diagnostics=measured,initial_diagnostics=diagnostics(normalized,reference),
        independent_agreement=independent_agreement(measured),
        edge_policy='Discard both two-cycle margins; derivative interpolation stays inside observed centers',
        warning='First-order smooth-phase approximation; fixed-amplitude kernel, not a general deconvolution')
    return result,where,evidence
