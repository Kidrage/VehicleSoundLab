"""Independent complete post-fit identity scoring, not an estimator input."""
from native_chirp_audit_v1.wave import near


def check(linked,truth,stored):
    assigned=[]
    absent_hits=[]
    identities={}
    runs={}
    for window,frame in enumerate(linked['frames']):
        visible=[v for v in truth[window]['lines'] if v.get('visible',True)] if truth else []
        absent=[v for v in truth[window]['lines'] if not v.get('visible',True)] if truth else []
        for node in frame:
            selected=None
            if visible:
                distance=[abs(node['frequency_hz']-v['frequency_hz']) for v in visible]
                k=distance.index(min(distance))
                first=visible[k]
                separated=all(abs(first['frequency_hz']-v['frequency_hz'])>=6 for j,v in enumerate(visible) if j!=k)
                if distance[k]<=2 and separated:selected=first['index']
            assigned.append(dict(window=window,index=node['index'],track_id=node['track_id'],component=selected))
            if selected is not None:
                identities.setdefault(node['track_id'],set()).add(selected)
                runs.setdefault(selected,[]).append((window,node['track_id']))
            for v in absent:
                if abs(node['frequency_hz']-v['frequency_hz'])<=2:
                    absent_hits.append(dict(window=window,track_id=node['track_id'],absent_component=v['index'],
                        near_visible=any(abs(node['frequency_hz']-u['frequency_hz'])<=2 for u in visible)))
    components=[]
    if truth:
        for v in truth[0]['lines']:
            k=v['index']
            observations=sorted(runs.get(k,[]))
            # Run lengths from connected (window,identity) nodes, independently
            # of the estimator's track array and the original scorer's loop.
            points=set(observations)
            lengths=[]
            for i,identity in observations:
                if (i-1,identity) in points:continue
                end=i
                while (end+1,identity) in points:end+=1
                lengths.append(end-i+1)
            components.append(dict(component=k,first_frequency_hz=v['frequency_hz'],scored_nodes=len(observations),
                longest_correct_contiguous=max(lengths,default=0),track_ids=sorted({identity for _,identity in observations})))
    expected=dict(components=components,assignments=assigned,
        mixed_identity_tracks=[dict(track_id=k,components=sorted(v)) for k,v in sorted(identities.items()) if len(v)>1],
        absent_query_hits=absent_hits,unexplained_absent_query_hits=[v for v in absent_hits if not v['near_visible']],
        longest_track=max((len(v['windows']) for v in linked['tracks']),default=0),
        tracks_atleast5=sum(len(v['windows'])>=5 for v in linked['tracks']))
    assert expected==stored
    return expected
