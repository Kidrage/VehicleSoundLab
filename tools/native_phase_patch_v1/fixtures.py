"""Continuous known cubic sources and fixed missing/occluded/crossing controls."""
import copy
import numpy as np


def mixture(case,p):
    n,rate,count=p['frames'],p['sample_rate'],p['windows']
    t=np.arange(n*count)/rate
    if case=='crossing_pair':
        base=np.array([100.,148.])
        q=np.array([16.,-16.])
        curvature=np.zeros(2)
        amp=np.array([.1,.1])
        initial=np.array([.1,.9])
    else:
        base=np.asarray(p['base_hz'])
        q=base*np.asarray(p['moving'])*.05
        curvature=base*np.asarray(p['moving'])*(.015 if case=='cubic_control' else 0)
        amp=np.asarray(p['amplitude_L'])
        initial=np.asarray(p['phase_radians'])
        if case=='missing_component_neighbor':
            base=np.r_[base,199.7]
            q=np.r_[q,0.]
            curvature=np.r_[curvature,0.]
            amp=np.r_[amp,.06]
            initial=np.r_[initial,.4]
    angle=2*np.pi*(t[:,None]*base+.5*t[:,None]**2*q+t[:,None]**3*curvature/6)+initial
    gain=np.ones_like(angle)
    if case=='occluded_component':gain[n*5:n*6,5]=0
    if case=='missing_component_neighbor':gain[:,5]=0
    x=np.column_stack(((np.cos(angle)*gain)@amp,
        (np.cos(angle+p['right_phase_radians'])*gain)@(amp*p['right_gain'])))
    truth=[]
    for i in range(count):
        at=(i+.5)*n/rate
        phases=2*np.pi*(base*at+.5*q*at*at+curvature*at**3/6)+initial
        frequencies=base+q*at+.5*curvature*at*at
        rates=q+curvature*at
        lines=[]
        for k in range(len(base)):
            visible=not(k==5 and (case=='missing_component_neighbor' or case=='occluded_component' and i==5))
            lines.append(dict(index=k,frequency_hz=float(frequencies[k]),chirp_hz_per_second=float(rates[k]),
                curvature_hz_per_second2=float(curvature[k]),phase_at_midpoint_LR=[float(phases[k]),float(phases[k]+p['right_phase_radians'])],
                amplitude_LR=[float(amp[k]),float(amp[k]*p['right_gain'])],visible=visible,eligible=visible))
        truth.append(dict(success=True,lines=lines,diagnostic_only=True))
    return x,truth


def annotate_previous_truth(case,rows,p):
    result=copy.deepcopy(rows)
    omega=2*np.pi*p['FM']['modulation_hz']
    for i,row in enumerate(result):
        at=(i+.5)*p['frames']/p['sample_rate']
        for k,line in enumerate(row['lines']):
            dev=p['base_hz'][k]/p['FM']['reference_hz']*p['FM']['deviation_at_reference_hz']*p['moving'][k]*(case in ['fm_only','am_fm'])
            line.update(curvature_hz_per_second2=float(-dev*omega**2*np.sin(omega*at)),visible=True)
    return result
