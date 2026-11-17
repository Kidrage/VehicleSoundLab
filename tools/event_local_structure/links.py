"""Mutually unique adjacent observations, with gaps and ambiguity retained."""
import numpy as np
from .spectrum import EDGES


def graph(left,right,radius):
    a=np.asarray(left,dtype=float);b=np.asarray(right,dtype=float)
    if a.ndim!=1 or b.ndim!=1 or not np.isfinite(a).all() or not np.isfinite(b).all() or not np.isfinite(radius) or radius<=0:
        raise ValueError('Finite frequency lists and positive radius required')
    edges=abs(a[:,None]-b[None,:])<=radius
    incoming=edges.sum(axis=0);outgoing=edges.sum(axis=1)
    result=[]
    for i in range(len(a)):
        matches=np.flatnonzero(edges[i])
        state='absent' if not len(matches) else 'ambiguous'
        chosen=None
        if len(matches)==1 and incoming[matches[0]]==1:
            state='unique';chosen=int(matches[0])
        result.append(dict(left=i,state=state,right=chosen,candidates=matches.tolist()))
    return result


def links(rows,df,window_seconds):
    result=[]
    for left,right in zip(rows[:-1],rows[1:]):
        dt=right['centre_seconds']-left['centre_seconds']
        if dt<=0:raise ValueError('Increasing native observations required')
        radius=1.5*df+1500*dt
        matches=graph([p['hz'] for p in left['peaks']],[p['hz'] for p in right['peaks']],radius)
        for item in matches:
            a=left['peaks'][item['left']]
            item.update(left_frame=left['frame'],right_frame=right['frame'],
                centre_interval_seconds=dt,radius_hz=radius,left_hz=a['hz'])
            if item['state']=='unique':
                b=right['peaks'][item['right']]
                c1=np.array(a['coefficient_real_LR'])+1j*np.array(a['coefficient_imag_LR'])
                c2=np.array(b['coefficient_real_LR'])+1j*np.array(b['coefficient_imag_LR'])
                predicted=.5*(a['hz']+b['hz'])*dt
                residual=np.angle(c2*c1.conjugate()*np.exp(-2j*np.pi*predicted))/(2*np.pi)
                item.update(right_hz=b['hz'],change_hz=b['hz']-a['hz'],
                    frequency_slope_hz_per_second=(b['hz']-a['hz'])/dt,
                    phase_residual_cycles_LR=residual.tolist(),
                    phase_summary_eligible=a['phase_summary_eligible'] and b['phase_summary_eligible'],
                    half_power_width_hz_LRwindows=[a['half_power_width_hz'],b['half_power_width_hz']])
            result.append(item)
    return result


def summarize(rows,connections,df):
    summaries=[]
    for lo,hi in EDGES:
        peaks=[p for row in rows for p in row['peaks'] if lo<=p['hz']<hi]
        chosen=[r for r in connections if lo<=r['left_hz']<hi]
        unique=[r for r in chosen if r['state']=='unique']
        phase=[r for r in unique if r['phase_summary_eligible']]
        widths=[p['half_power_width_hz'] for p in peaks if p['half_power_width_hz'] is not None]
        residual=np.array([r['phase_residual_cycles_LR'] for r in phase])
        summaries.append(dict(band_hz=[lo,hi],observed_peaks=len(peaks),link_opportunities=len(chosen),
            unique_links=len(unique),absent_links=sum(r['state']=='absent' for r in chosen),
            ambiguous_links=sum(r['state']=='ambiguous' for r in chosen),phase_links=len(phase),
            median_half_power_width_hz=float(np.median(widths)) if widths else None,
            median_half_power_width_native_bins=float(np.median(widths)/df) if widths else None,
            unique_fraction=float(len(unique)/len(chosen)) if chosen else None,
            phase_residual_RMS_cycles_LR=np.sqrt(np.mean(residual**2,axis=0)).tolist() if len(phase) else None,
            phase_resultant_magnitude_LR=abs(np.exp(2j*np.pi*residual).mean(axis=0)).tolist() if len(phase) else None,
            qualification='Descriptive finite observations; overlap, selection, finite noise and neighbouring lines confound identity and memory'))
    return summaries
