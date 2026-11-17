"""Follow only a contiguous mutually unique peak component from an explicit anchor."""
import numpy as np


def follow(rows,df,anchor_seconds,anchor_hz,band_hz,anchor_radius=35.,maximum_slew=2000.):
    if not rows or not np.isfinite([df,anchor_seconds,anchor_hz,anchor_radius,maximum_slew,*band_hz]).all():
        raise ValueError('Finite observed rows, anchor, band and limits required')
    lo,hi=band_hz
    if not 0<lo<hi<24000 or not lo<=anchor_hz<hi or min(df,anchor_radius,maximum_slew)<=0:
        raise ValueError('Positive limits and anchor within acoustic band required')
    times=np.array([r['centre_seconds'] for r in rows])
    if not np.all(np.diff(times)>0) or not times[0]<=anchor_seconds<=times[-1]:
        raise ValueError('Anchor must lie in finite increasing observation support')
    anchor=int(np.argmin(abs(times-anchor_seconds)))
    def inventory(index):
        return [(j,p) for j,p in enumerate(rows[index]['peaks']) if lo<=p['hz']<hi]
    start=[(j,p) for j,p in inventory(anchor) if abs(p['hz']-anchor_hz)<=anchor_radius]
    if len(start)!=1:
        return dict(status='absent_anchor' if not start else 'ambiguous_anchor',points=[],
            anchor_frame=anchor,anchor_candidates=[j for j,_ in start],terminations=[])
    initial=dict(frame=anchor,peak=start[0][0],centre_seconds=float(times[anchor]),**start[0][1])
    points={anchor:initial};terminal=[]
    for direction in (-1,1):
        current=initial
        for index in range(anchor+direction,-1 if direction<0 else len(rows),direction):
            prior=current['frame'];dt=abs(times[index]-times[prior]);radius=.5*df+maximum_slew*dt
            nexts=[(j,p) for j,p in inventory(index) if abs(p['hz']-current['hz'])<=radius]
            record=dict(direction=direction,from_frame=prior,to_frame=index,radius_hz=float(radius),
                candidate_peaks=[j for j,_ in nexts])
            if len(nexts)!=1:
                record['reason']='absent' if not nexts else 'ambiguous_forward'
                terminal.append(record);break
            j,peak=nexts[0]
            reverse=[k for k,p in inventory(prior) if abs(p['hz']-peak['hz'])<=radius]
            if reverse!=[current['peak']]:
                record.update(reason='ambiguous_reverse',reverse_candidates=reverse)
                terminal.append(record);break
            current=dict(frame=index,peak=j,centre_seconds=float(times[index]),**peak)
            points[index]=current
        else:terminal.append(dict(direction=direction,reason='observation_boundary',from_frame=current['frame']))
    ordered=[points[k] for k in sorted(points)]
    return dict(status='contiguous_acoustic_component',anchor_frame=anchor,anchor_candidates=[start[0][0]],
        points=ordered,terminations=terminal,physical_identity_or_RPM=False,
        limitations='Geometric support only. An unresolved doublet or narrow stochastic resonance can follow a unique peak. Shared-window phases are not independent evidence of long-term memory.')
