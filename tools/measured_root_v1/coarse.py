"""Remove lattice quantization without letting one loud peak own the root."""
import numpy as np
from scipy import signal
from state_colour_v2.clock import peaks
from multicarrier_clock_v1.coarse import track as lattice_track


def selected_lines(hz, power, root, orders):
    frequencies,prominence=peaks(hz,power)
    if not len(frequencies):
        return np.array([]),np.array([]),np.array([])
    wanted=root*orders
    nearest=abs(wanted[:,None]-frequencies[None,:]).argmin(axis=1)
    supported=(abs(wanted-frequencies[nearest])<=np.maximum(6,.025*wanted))&(wanted>=35)&(wanted<1200)
    for column in range(len(orders)):
        if column:
            supported[column] &= not np.any((nearest[column]==nearest[:column])&supported[:column])
    return orders[supported],frequencies[nearest[supported]],prominence[nearest[supported]]


def track(observed,start,stop,anchor,plan):
    original=lattice_track(observed,start,stop,anchor,plan)
    if not original['rows']:
        return original
    selected=np.flatnonzero((observed['seconds']>=start-1e-8)&(observed['seconds']<=stop+1e-8))
    orders=np.asarray(plan['orders'])
    roots=[]
    evidence=[]
    for index,row in zip(selected,original['rows']):
        line,frequency,prominence=selected_lines(observed['hz'],observed['power_low'][:,index],row['measured_lattice_root_hz'],orders)
        if len(line)<plan['minimum_observed_lines']:
            return dict(status='missing_refinement_support',rows=[])
        measured=frequency/line
        weight=line**2*np.clip(prominence/16,.25,1)
        weight=np.minimum(weight,plan['precision_weight_median_cap']*np.median(weight))
        order=np.argsort(measured)
        median=measured[order[np.searchsorted(np.cumsum(weight[order]),weight.sum()/2)]]
        supported,_,_=selected_lines(observed['hz'],observed['power_low'][:,index],median,orders)
        if len(supported)<plan['minimum_observed_lines']:
            return dict(status='unsupported_measured_median',rows=[])
        roots.append(median)
        evidence.append(dict(orders=line.tolist(),measured_roots_hz=measured.tolist(),
            capped_precision_weights=weight.tolist(),median_root_hz=float(median)))
    rate=1/float(np.median(np.diff(observed['seconds'][selected])))
    smoothed=signal.sosfiltfilt(signal.butter(4,plan['smoothing_hz'],fs=rate,output='sos'),roots)
    for number,(index,row) in enumerate(zip(selected,original['rows'])):
        supported,_,_=selected_lines(observed['hz'],observed['power_low'][:,index],smoothed[number],orders)
        if len(supported)<plan['minimum_observed_lines']:
            # Preserve the already verified original support point; never
            # manufacture a missing observation or interpolate across a gap.
            smoothed[number]=row['root_hz']
            evidence[number]['fallback_original_supported_root']=True
        else:
            evidence[number]['fallback_original_supported_root']=False
    times=observed['seconds'][selected]
    if np.max(abs(np.diff(np.log2(smoothed))/np.diff(times)))>plan['maximum_octaves_per_second']+1e-8:
        return dict(status='refined_consensus_disconnected',rows=[])
    result=dict(original)
    result['rows']=[dict(row,original_smoothed_root_hz=row['root_hz'],root_hz=float(smoothed[number]),
        measured_refinement=evidence[number]) for number,row in enumerate(original['rows'])]
    result['policy']='Original no-gap measured lattice, capped-precision median of distinct measured peak roots, same4Hz smoother and support/velocity bounds; no physical RPM identity'
    result['root_estimator']='measured_capped_precision_median'
    return result
