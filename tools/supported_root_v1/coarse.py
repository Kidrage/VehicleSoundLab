"""Preserve a measured path while constraining continuous root proposals."""
import numpy as np
from scipy import signal
from state_colour_v2.clock import peaks
from multicarrier_clock_v1.coarse import track as lattice_track
from measured_root_v1.coarse import selected_lines
from .feasible import project


def track(observed,start,stop,anchor,plan):
    original=lattice_track(observed,start,stop,anchor,plan)
    if not original['rows']:
        return original
    selected=np.flatnonzero((observed['seconds']>=start-1e-8)&(observed['seconds']<=stop+1e-8))
    orders=np.asarray(plan['orders'])
    roots=[]
    evidence=[]
    measured_frequencies=[]
    for index,row in zip(selected,original['rows']):
        line,frequency,prominence=selected_lines(observed['hz'],observed['power_low'][:,index],row['measured_lattice_root_hz'],orders)
        if len(line)<plan['minimum_observed_lines']:
            return dict(status='missing_refinement_support',rows=[])
        measured=frequency/line
        weight=line**2*np.clip(prominence/16,.25,1)
        weight=np.minimum(weight,plan['precision_weight_median_cap']*np.median(weight))
        order=np.argsort(measured)
        median=measured[order[np.searchsorted(np.cumsum(weight[order]),weight.sum()/2)]]
        frequencies,_=peaks(observed['hz'],observed['power_low'][:,index])
        measured_frequencies.append(frequencies)
        try:
            projected,proof=project(median,frequencies,orders,plan['root_range_hz'],plan['minimum_observed_lines'])
        except ValueError as exc:
            return dict(status='no_measured_projection_region',rows=[],reason=str(exc),seconds=row['seconds'])
        roots.append(projected)
        evidence.append(dict(orders=line.tolist(),measured_roots_hz=measured.tolist(),
            capped_precision_weights=weight.tolist(),median_root_hz=float(median),median_projection=proof))
    rate=1/float(np.median(np.diff(observed['seconds'][selected])))
    smoothed=signal.sosfiltfilt(signal.butter(4,plan['smoothing_hz'],fs=rate,output='sos'),roots)
    for number,frequencies in enumerate(measured_frequencies):
        try:
            smoothed[number],proof=project(smoothed[number],frequencies,orders,plan['root_range_hz'],plan['minimum_observed_lines'])
        except ValueError as exc:
            return dict(status='no_smoothed_projection_region',rows=[],reason=str(exc))
        evidence[number]['smoothed_projection']=proof
    times=observed['seconds'][selected]
    if np.max(abs(np.diff(np.log2(smoothed))/np.diff(times)))>plan['maximum_octaves_per_second']+1e-8:
        return dict(status='refined_consensus_disconnected',rows=[])
    result=dict(original)
    result['rows']=[dict(row,original_smoothed_root_hz=row['root_hz'],root_hz=float(smoothed[number]),
        measured_refinement=evidence[number]) for number,row in enumerate(original['rows'])]
    result['policy']='Original no-gap lattice; continuous capped-precision median and4Hz result each projected into distinct-measured nearest-peak support; unchanged tolerances and velocity bound'
    result['root_estimator']='supported_continuous_peak_median'
    return result
