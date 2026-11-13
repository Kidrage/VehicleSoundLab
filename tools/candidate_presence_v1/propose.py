"""Causal candidate cells from previously accepted observed polynomial patches."""
import math
import statistics


def propose(inventory,initial,previous,frames=12000,rate=48000):
    df=rate/frames
    step=frames/rate
    detected=set(inventory['bin'])
    minimum_cells=round(6/df)
    proposals={}
    provenance=[]
    for index,line in enumerate(previous.get('lines',[]) if previous else []):
        if not line['eligible']:continue
        f,q,a=line['frequency_hz'],line['chirp_hz_per_second'],line.get('curvature_hz_per_second2',0.)
        prediction=f+q*step+.5*a*step*step
        predicted_rate=q+a*step
        if not math.isfinite(prediction) or not math.isfinite(predicted_rate):
            raise ValueError('Previously accepted patches must have finite forecasts')
        cell=int(round(prediction/df))
        record=dict(previous_line_index=index,predicted_frequency_hz=prediction,predicted_rate_hzs=predicted_rate,native_bin=cell)
        if not 30<=cell*df<7000:
            record['state']='out_of_domain'
        elif cell in detected:
            record['state']='already_detected'
        elif any(abs(cell-v)<minimum_cells for v in detected):
            record['state']='ambiguous_near_detected'
        else:
            record['state']='proposed'
            proposals.setdefault(cell,[]).append(record)
        provenance.append(record)
    # Distinct propagated cells can also be closer than the detector's spacing.
    # Preserve all proposals as ambiguous instead of choosing a strongest/best.
    conflicts={cell for cell in proposals if any(other!=cell and abs(other-cell)<minimum_cells for other in proposals)}
    for record in provenance:
        if record['state']=='proposed' and record['native_bin'] in conflicts:record['state']='ambiguous_between_proposals'
    added=sorted(cell for cell in proposals if cell not in conflicts)
    cells=sorted(detected|set(added))
    original=dict(zip(inventory['bin'],zip(inventory['hz'],initial['initial_chirp'])))
    frequencies=[]
    rates=[]
    for cell in cells:
        if cell in original:
            f,q=original[cell]
        else:
            f=cell*df
            q=statistics.mean(v['predicted_rate_hzs'] for v in proposals[cell])
        frequencies.append(f)
        rates.append(q)
    return dict(inventory=dict(bin=cells,hz=frequencies),initial_chirp=rates,added_bins=added,provenance=provenance,
        minimum_cell_spacing=minimum_cells,truth_or_future_input=False)
