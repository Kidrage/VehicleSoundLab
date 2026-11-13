"""Conservative frequency/rate correspondence with explicit breaks and no gap fill."""
import statistics


def link(windows,plan):
    step=plan['hop']/plan['sample_rate'];frames=[];transitions=[];next_id=0
    for number,window in enumerate(windows):
        nodes=[dict(row) for row in window['lines'] if row['eligible']]
        inherited={};edges=[]
        if frames:
            for i,a in enumerate(frames[-1]):
                for j,b in enumerate(nodes):
                    forward=b['frequency_hz']-(a['frequency_hz']+step*a['chirp_hz_per_second'])
                    backward=a['frequency_hz']-(b['frequency_hz']-step*b['chirp_hz_per_second'])
                    dq=b['chirp_hz_per_second']-a['chirp_hz_per_second']
                    if max(abs(forward),abs(backward))<=plan['link_prediction_error_hz'] and abs(dq)<=plan['link_chirp_difference_hz_per_second']:
                        edges.append(dict(previous=i,current=j,forward_error_hz=forward,backward_error_hz=backward,chirp_difference=dq))
            for edge in edges:
                i,j=edge['previous'],edge['current']
                if sum(e['previous']==i for e in edges)==sum(e['current']==j for e in edges)==1:
                    inherited[j]=frames[-1][i]['track_id']
            transitions.append(dict(previous_window=number-1,current_window=number,edges=edges))
        for j,node in enumerate(nodes):
            if j in inherited:node.update(track_id=inherited[j],predecessor='unique')
            else:
                node.update(track_id=next_id,predecessor='ambiguous' if any(e['current']==j for e in edges) else 'none');next_id+=1
            node['window']=number
        frames.append(nodes)
    tracks=[]
    for identity in range(next_id):
        rows=[node for frame in frames for node in frame if node['track_id']==identity]
        frequencies=[row['frequency_hz'] for row in rows];rates=[row['chirp_hz_per_second'] for row in rows]
        kind='unresolved'
        if len(rows)>=plan['minimum_classification_windows']:
            if max(map(abs,rates))<=plan['stationary_maximum_chirp_hz_per_second']:kind='locally_stationary'
            elif statistics.median(map(abs,rates))>=plan['moving_minimum_median_chirp_hz_per_second'] and max(frequencies)-min(frequencies)>=plan['moving_minimum_frequency_span_hz'] and (min(rates)>0 or max(rates)<0):kind='locally_moving'
        tracks.append(dict(track_id=identity,windows=[r['window'] for r in rows],
            frequencies_hz=frequencies,chirps_hz_per_second=rates,classification=kind))
    return dict(frames=frames,transitions=transitions,tracks=tracks,
        scope='Conditional independent local-chirp correspondence, not source separation, actual RPM or common phase')
