"""Truth used only after fitting to report every qualified/unknown identity region."""


def score(linked,truth,frequency_radius=2.,separation=6.):
    counts={}
    labels={}
    assignments=[]
    absent_hits=[]
    for i,frame in enumerate(linked['frames']):
        visible=[v for v in truth[i]['lines'] if v.get('visible',True)] if truth else []
        absent=[v for v in truth[i]['lines'] if not v.get('visible',True)] if truth else []
        for node in frame:
            chosen=None
            if visible:
                closest=sorted(visible,key=lambda v:abs(node['frequency_hz']-v['frequency_hz']))
                first=closest[0]
                separated=len(closest)==1 or min(abs(v['frequency_hz']-first['frequency_hz']) for v in visible if v is not first)>=separation
                if abs(node['frequency_hz']-first['frequency_hz'])<=frequency_radius and separated:chosen=first['index']
            assignments.append(dict(window=i,index=node['index'],track_id=node['track_id'],component=chosen))
            if chosen is not None:
                labels.setdefault(node['track_id'],set()).add(chosen)
                counts.setdefault(chosen,[]).append((i,node['track_id']))
            for target in absent:
                if abs(node['frequency_hz']-target['frequency_hz'])<=frequency_radius:
                    absent_hits.append(dict(window=i,track_id=node['track_id'],absent_component=target['index'],
                        near_visible=any(abs(node['frequency_hz']-v['frequency_hz'])<=frequency_radius for v in visible)))
    component=[]
    if truth:
        for target in truth[0]['lines']:
            k=target['index']
            observations=sorted(counts.get(k,[]))
            best=run=0
            last=(-2,None)
            for i,identity in observations:
                run=run+1 if i==last[0]+1 and identity==last[1] else 1
                best=max(best,run)
                last=(i,identity)
            component.append(dict(component=k,first_frequency_hz=target['frequency_hz'],
                scored_nodes=len(observations),longest_correct_contiguous=best,
                track_ids=sorted({v for _,v in observations})))
    return dict(components=component,assignments=assignments,
        mixed_identity_tracks=[dict(track_id=k,components=sorted(v)) for k,v in sorted(labels.items()) if len(v)>1],
        absent_query_hits=absent_hits,unexplained_absent_query_hits=[v for v in absent_hits if not v['near_visible']],
        longest_track=max((len(v['windows']) for v in linked['tracks']),default=0),
        tracks_atleast5=sum(len(v['windows'])>=5 for v in linked['tracks']))
