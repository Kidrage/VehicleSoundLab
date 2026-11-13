"""Independent scalar boundary graph and identity inheritance; no model fitting."""
import math
from native_chirp_audit_v1.wave import near


def check(rows,actual):
    frames=[]
    next_id=0
    count=0
    for number,row in enumerate(rows):
        nodes=[dict(v) for v in row['lines'] if v['eligible']]
        edges=[]
        inherited={}
        if number:
            for i,a in enumerate(frames[-1]):
                for j,b in enumerate(nodes):
                    def at(v,time):
                        f,q,c=v['frequency_hz'],v['chirp_hz_per_second'],v.get('curvature_hz_per_second2',0.)
                        return (f+q*time+c*time*time/2,
                            [phase/math.tau+f*time+q*time*time/2+c*time**3/6 for phase in v['phase_at_midpoint_LR']],q+c*time)
                    fa,pa,qa=at(a,.125)
                    fb,pb,qb=at(b,-.125)
                    phase=[(y-x+.5)%1-.5 for x,y in zip(pa,pb)]
                    if abs(fb-fa)<=.5 and max(abs(v) for v in phase)<=.125:
                        edges.append(dict(previous=i,current=j,frequency_boundary_error_hz=fb-fa,
                            phase_boundary_error_cycles_LR=phase,rate_boundary_difference_hzs=qb-qa))
            stored=actual['transitions'][number-1]
            assert stored['previous_window']==number-1 and stored['current_window']==number and len(stored['edges'])==len(edges)
            for expected,observed in zip(edges,stored['edges']):
                assert expected['previous']==observed['previous'] and expected['current']==observed['current']
                for key in ['frequency_boundary_error_hz','phase_boundary_error_cycles_LR','rate_boundary_difference_hzs']:near(expected[key],observed[key])
            count+=len(edges)
            for edge in edges:
                i,j=edge['previous'],edge['current']
                if sum(v['previous']==i for v in edges)==sum(v['current']==j for v in edges)==1:inherited[j]=frames[-1][i]['track_id']
        for j,node in enumerate(nodes):
            if j in inherited:node.update(track_id=inherited[j],predecessor='unique',window=number)
            else:
                node.update(track_id=next_id,predecessor='ambiguous' if any(v['current']==j for v in edges) else 'none',window=number)
                next_id+=1
        assert nodes==actual['frames'][number]
        frames.append(nodes)
    assert len(actual['tracks'])==next_id and len(actual['transitions'])==len(rows)-1
    for identity in range(next_id):
        nodes=[v for frame in frames for v in frame if v['track_id']==identity]
        assert actual['tracks'][identity]==dict(track_id=identity,windows=[v['window'] for v in nodes],
            frequencies_hz=[v['frequency_hz'] for v in nodes],chirps_hz_per_second=[v['chirp_hz_per_second'] for v in nodes],
            curvatures_hzs2=[v.get('curvature_hz_per_second2',0.) for v in nodes])
    assert actual['frequency_boundary_limit_hz']==.5 and actual['phase_boundary_limit_cycles']==.125
    return dict(tracks=next_id,edges=count)
