"""Native upper peak rejection census, separate from source/model selection."""
import numpy as np
from scipy.signal import find_peaks


def measure(audio,plan):
    n=plan['frames'];rate=plan['sample_rate']
    if audio.shape!=(n,2) or not np.isfinite(audio).all():raise ValueError('Expected finite native stereo tile')
    win=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    spectrum=np.fft.rfft(audio*win[:,None],axis=0)
    cells=abs(spectrum)**2*2/(n*np.sum(win*win));cells[[0,-1]]*=.5
    total=cells.sum(axis=1);df=rate/n;freq=np.arange(len(total))*df
    log=10*np.log10(np.maximum(total,np.finfo(float).tiny))
    peaks,props=find_peaks(log,prominence=0,distance=max(1,round(plan['peak_spacing_hz']/df)))
    old=(freq>=plan['old_domain_hz'][0])&(freq<plan['old_domain_hz'][1])
    old_max=float(total[old].max(initial=0));factor=10**(plan['floor_db_relative_to_maximum']/10)
    bands=[];rows=[]
    for b,(lo,hi) in enumerate(plan['upper_bands_hz']):
        mask=(freq>=lo)&(freq<hi);maximum=float(total[mask].max(initial=0));sums=cells[mask].sum(axis=0)
        cross=(spectrum[mask,0]*np.conj(spectrum[mask,1])).sum()*2/(n*np.sum(win*win))
        geometric=np.exp(np.mean(np.log(total[mask]))) if np.all(total[mask]>0) else 0.
        mean=float(np.mean(total[mask]));median=float(np.median(total[mask]))
        bands.append(dict(band_hz=[lo,hi],power_LR=sums.tolist(),maximum_cell_power=maximum,
            maximum_relative_to_old_db=float(10*np.log10(maximum/old_max)) if maximum>0 and old_max>0 else None,
            maximum_over_median_db=float(10*np.log10(maximum/median)) if median>0 else None,
            flatness=float(geometric/mean) if mean>0 else None,
            centroid_hz=float(np.dot(freq[mask],total[mask])/total[mask].sum()) if total[mask].sum()>0 else None,
            normalized_cross_LR=[float(cross.real/np.sqrt(np.prod(sums))),float(cross.imag/np.sqrt(np.prod(sums)))] if np.all(sums>0) else None))
        for j,k in enumerate(peaks):
            if not lo<=freq[k]<hi:continue
            den=log[k-1]-2*log[k]+log[k+1]
            delta=np.clip(.5*(log[k-1]-log[k+1])/den,-.5,.5) if den else 0.
            prominent=bool(props['prominences'][j]>=plan['peak_prominence_db'])
            old_floor=bool(total[k]>=old_max*factor and total[k]>0)
            local_floor=bool(total[k]>=maximum*factor and total[k]>0)
            old_domain=bool(old[k])
            rows.append(dict(band=b,bin=int(k),frequency_hz=float((k+delta)*df),power_LR=cells[k].tolist(),
                prominence_db=float(props['prominences'][j]),prominence_ok=prominent,
                old_floor_ok=old_floor,local_floor_ok=local_floor,old_domain_ok=old_domain,
                old_accepted=bool(prominent and old_floor and old_domain),local_candidate=bool(prominent and local_floor)))
    for i,band in enumerate(bands):
        subset=[v for v in rows if v['band']==i]
        band['counts']={name:sum(v[name] for v in subset) for name in ['prominence_ok','old_floor_ok','local_floor_ok','old_domain_ok','old_accepted','local_candidate']}
        band['counts']['raw_maxima']=len(subset)
        band['counts']['prominent_rejected_by_old_floor']=sum(v['prominence_ok'] and not v['old_floor_ok'] for v in subset)
        band['counts']['prominent_outside_old_domain']=sum(v['prominence_ok'] and not v['old_domain_ok'] for v in subset)
    return dict(old_maximum_cell_power=old_max,bands=bands,peaks=rows),dict(audio=audio,spectrum=spectrum,cells=cells,total=total,logged=log)
