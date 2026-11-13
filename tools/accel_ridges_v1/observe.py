"""Native guided spectral-peak correspondence; no synthesis or engine clock."""
import numpy as np
from scipy.signal import find_peaks


def inventory(audio,plan):
    n=len(audio);rate=plan['rate'];df=rate/n
    if audio.shape!=(plan['tile_frames'],2) or not np.isfinite(audio).all():raise ValueError('Expected native finite stereo tile')
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    transform=np.fft.rfft(audio*window[:,None],axis=0)
    power=abs(transform)**2*2/(n*np.sum(window*window));power[[0,-1]]*=.5
    total=power.sum(axis=1);logged=10*np.log10(np.maximum(total,np.finfo(float).tiny))
    distance=max(1,round(plan['peak_spacing_hz']/df))
    indices,properties=find_peaks(logged,prominence=plan['peak_prominence_db'],distance=distance)
    lo,hi=plan['inventory_hz'];native=np.arange(len(total))*df
    band=(native>=lo)&(native<hi);maximum=total[band].max(initial=0)
    selected=band[indices]&(total[indices]>=maximum*10**(plan['peak_floor_db_relative_to_maximum']/10))
    indices=indices[selected];prominence=properties['prominences'][selected]
    denominator=logged[indices-1]-2*logged[indices]+logged[indices+1]
    delta=np.divide(.5*(logged[indices-1]-logged[indices+1]),denominator,
                    out=np.zeros(len(indices)),where=denominator!=0)
    frequencies=(indices+np.clip(delta,-.5,.5))*df
    return dict(bin=indices.tolist(),hz=frequencies.tolist(),power_LR=power[indices].tolist(),
                prominence_db=prominence.tolist(),native_bin_hz=df)


def associate(reference,observed,ratio,df,plan):
    reference=np.asarray(reference);observed=np.asarray(observed)
    expected=reference*ratio
    radius=df*(1+ratio)+expected*(2**(.5/plan['guide_bins_per_octave'])-1)
    edges=abs(expected[:,None]-observed[None,:])<=radius[:,None]
    rows=edges.sum(axis=1);columns=edges.sum(axis=0);states=[];chosen=[]
    for i in range(len(reference)):
        candidates=np.flatnonzero(edges[i])
        if rows[i]==1 and columns[candidates[0]]==1:states.append('unique');chosen.append(int(candidates[0]))
        else:states.append('absent' if rows[i]==0 else 'ambiguous');chosen.append(None)
    return dict(expected_hz=expected.tolist(),radius_hz=radius.tolist(),
                state=states,chosen=chosen,edges=edges.astype(int).tolist())


def longest(indices):
    best=run=0;previous=-2
    for i in indices:run=run+1 if i==previous+1 else 1;best=max(best,run);previous=i
    return best


def correspondence(inventories,guides,plan):
    if len(inventories)!=len(guides) or not inventories:raise ValueError('Unmatched observation/guide')
    lo,hi=plan['reference_hz'];first=inventories[0]
    refs=[i for i,f in enumerate(first['hz']) if lo<=f<hi]
    reference=[first['hz'][i] for i in refs];rows=[]
    for i,(observed,guide) in enumerate(zip(inventories,guides)):
        ratio=guide['ratio']
        moving=associate(reference,observed['hz'],ratio,first['native_bin_hz'],plan)
        fixed=associate(reference,observed['hz'],1.,first['native_bin_hz'],plan)
        eligible=[bool(i and guide['supported'] and abs(a-b)>2*max(x,y)) for a,b,x,y in
                  zip(moving['expected_hz'],fixed['expected_hz'],moving['radius_hz'],fixed['radius_hz'])]
        rows.append(dict(tile=i,ratio=ratio,guide_supported=guide['supported'],moving=moving,fixed=fixed,eligible=eligible))
    classes=[]
    for k,f in enumerate(reference):
        used=[i for i,row in enumerate(rows) if row['eligible'][k]]
        hits={name:[i for i in used if rows[i][name]['state'][k]=='unique'] for name in ['moving','fixed']}
        fraction={name:len(indices)/len(used) if used else 0 for name,indices in hits.items()}
        label='uncertain'
        if len(used)>=5:
            for name,other in [('moving','fixed'),('fixed','moving')]:
                if fraction[name]>=.8 and fraction[other]<=.2 and longest(hits[name])>=5:label=name
        classes.append(dict(reference_inventory_index=refs[k],reference_hz=f,classification=label,
            eligible_tiles=used,hypothesis_unique_tiles=hits,support_fraction=fraction,
            longest_consecutive={name:longest(indices) for name,indices in hits.items()}))
    return dict(reference_hz=reference,rows=rows,classes=classes,
                counts={name:sum(row['classification']==name for row in classes) for name in ['moving','fixed','uncertain']})
