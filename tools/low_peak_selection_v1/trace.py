"""Expose the selection pipeline used by the frozen independent-mode fitter."""
import numpy as np
from scipy import signal
from idle_modal_v1.modal import peaks


def stages(power,rate,n,plan):
    db=10*np.log10(power+1e-30)
    raw=signal.find_peaks(db)[0]
    spaced=signal.find_peaks(db,distance=max(1,round(plan['peak_spacing_hz']*n/rate)))[0]
    prominent=signal.find_peaks(db,distance=max(1,round(plan['peak_spacing_hz']*n/rate)),
        prominence=plan['peak_prominence_db'])[0]
    frequency=np.arange(len(power))*rate/n;lo,hi=plan['modal_band_hz']
    band=prominent[(frequency[prominent]>=lo)&(frequency[prominent]<hi)]
    floor=band[power[band]>=power[band].max()*10**(plan['peak_floor_db_relative_to_maximum']/10)] if len(band) else band
    capped=floor[np.argsort(power[floor])[::-1]][:plan['maximum_modes']]
    membership={name:set(map(int,value)) for name,value in [('distance',spaced),('prominence',prominent),('band',band),('floor',floor),('cap',capped)]}
    q=np.log(power+1e-30);rows=[]
    prominence=signal.peak_prominences(db,raw)[0]
    for k,index in enumerate(raw):
        denominator=q[index-1]-2*q[index]+q[index+1]
        delta=.5*(q[index-1]-q[index+1])/denominator if denominator else 0.
        f=(index+np.clip(delta,-.5,.5))*rate/n
        passed={name:int(index) in values for name,values in membership.items()}
        first=next((name for name,value in passed.items() if not value),'kept')
        rows.append(dict(bin=int(index),frequency_hz=float(f),power=float(power[index]),
            prominence_db=float(prominence[k]),passed=passed,first_rejection=first))
    final=sorted(row['frequency_hz'] for row in rows if row['passed']['cap'])
    return rows,final


def window(audio,rate,plan):
    n=len(audio);w=signal.windows.hann(n,sym=False)
    z=np.fft.rfft(audio*w[:,None],axis=0);power=np.sum(abs(z)**2,axis=1)
    rows,final=stages(power,rate,n,plan)
    original=peaks(audio,rate,plan)
    assert np.array_equal(np.asarray(final),original)
    f=np.fft.rfftfreq(n,1/rate);mask=(f>=30)&(f<120);ix=np.flatnonzero(mask)[np.argmax(power[mask])]
    return dict(raw_peaks=rows,final_frequencies_hz=final,
        strongest_low_native_bin_hz=float(f[ix]),strongest_low_native_bin_power=float(power[ix]),
        original_selector_exact=True)


def anchor(trace,f,radius):
    kept=[g for g in trace['final_frequencies_hz'] if abs(g-f)<=radius]
    nearby=[row for row in trace['raw_peaks'] if abs(row['frequency_hz']-f)<=radius]
    nearest=min(trace['raw_peaks'],key=lambda row:abs(row['frequency_hz']-f),default=None)
    status='supported' if len(kept)==1 else ('ambiguous' if len(kept)>1 else 'absent')
    return dict(anchor_hz=float(f),status=status,final_candidates_hz=kept,raw_candidates=nearby,
        absence_reason=None if kept else ('no_raw_maximum_in_anchor_radius' if not nearby else 'raw_maxima_rejected'),
        nearest_raw_peak_not_identity=nearest)
