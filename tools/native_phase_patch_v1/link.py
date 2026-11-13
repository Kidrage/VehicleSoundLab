"""Adjacent-patch boundary agreement with explicit ambiguity and no gap bridging."""
import numpy as np


def boundary(line,time):
    f=line['frequency_hz']
    q=line['chirp_hz_per_second']
    a=line.get('curvature_hz_per_second2',0.)
    frequency=f+q*time+.5*a*time*time
    phase=np.asarray(line['phase_at_midpoint_LR'])/(2*np.pi)+f*time+.5*q*time*time+a*time**3/6
    return frequency,phase,q+a*time


def link(rows,plan):
    step=plan['hop']/plan['sample_rate']
    half=step/2
    frequency_limit=plan['link_prediction_error_hz']
    phase_limit=frequency_limit*step
    frames,transitions=[],[]
    next_id=0
    for number,row in enumerate(rows):
        nodes=[dict(v) for v in row['lines'] if v['eligible']]
        edges=[]
        inherited={}
        if number:
            for i,a in enumerate(frames[-1]):
                fa,pa,qa=boundary(a,half)
                for j,b in enumerate(nodes):
                    fb,pb,qb=boundary(b,-half)
                    dp=(pb-pa+.5)%1-.5
                    if abs(fb-fa)<=frequency_limit and max(abs(dp))<=phase_limit:
                        edges.append(dict(previous=i,current=j,frequency_boundary_error_hz=float(fb-fa),
                            phase_boundary_error_cycles_LR=dp.tolist(),rate_boundary_difference_hzs=float(qb-qa)))
            for edge in edges:
                i,j=edge['previous'],edge['current']
                if sum(v['previous']==i for v in edges)==sum(v['current']==j for v in edges)==1:
                    inherited[j]=frames[-1][i]['track_id']
            transitions.append(dict(previous_window=number-1,current_window=number,edges=edges))
        for j,node in enumerate(nodes):
            if j in inherited:node.update(track_id=inherited[j],predecessor='unique',window=number)
            else:
                node.update(track_id=next_id,predecessor='ambiguous' if any(v['current']==j for v in edges) else 'none',window=number)
                next_id+=1
        frames.append(nodes)
    tracks=[]
    for identity in range(next_id):
        nodes=[v for frame in frames for v in frame if v['track_id']==identity]
        tracks.append(dict(track_id=identity,windows=[v['window'] for v in nodes],
            frequencies_hz=[v['frequency_hz'] for v in nodes],chirps_hz_per_second=[v['chirp_hz_per_second'] for v in nodes],
            curvatures_hzs2=[v.get('curvature_hz_per_second2',0.) for v in nodes]))
    return dict(frames=frames,transitions=transitions,tracks=tracks,frequency_boundary_limit_hz=frequency_limit,
        phase_boundary_limit_cycles=phase_limit,scope='Independent polynomial patch boundary agreement, NOT source identity or shared engine phase')
