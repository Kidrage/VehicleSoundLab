"""Current-wave conditional null tests and unique predecessor acceptance."""
import copy
import numpy as np
from scipy.linalg import lstsq
from native_phase_patch_v1.basis import geometry
from native_phase_patch_v1.link import boundary


def accept(raw,arrays,audio,proposal,previous,frames=12000,rate=48000):
    result=copy.deepcopy(raw)
    if not raw['lines']:return result,dict(tests=[],edges=[],note='Empty or overflow hypothesis retained')
    n,m=len(audio),len(raw['lines'])
    t=np.arange(n)/rate-n/(2*rate)
    w=np.sqrt((.5-.5*np.cos(2*np.pi*np.arange(n)/n))/n)
    p=arrays['parameters']
    theta=2*np.pi*t[:,None]*arrays['nominal']+geometry(t,n/rate)@p.reshape(3,m)
    design=np.column_stack((np.cos(theta),np.sin(theta),np.ones(n)))
    weighted=w[:,None]*design
    target=w[:,None]*audio
    full_residual=weighted@arrays['coefficients']-target
    full_cost=np.sum(full_residual**2,axis=0)
    added=set(proposal['added_bins'])
    edges=[]
    tests=[]
    previous_lines=previous.get('lines',[]) if previous else []
    for i,a in enumerate(previous_lines):
        if not a['eligible']:continue
        fa,pa,_=boundary(a,.125)
        for j,b in enumerate(raw['lines']):
            if not b['eligible']:continue
            fb,pb,_=boundary(b,-.125)
            dp=(pb-pa+.5)%1-.5
            if abs(fb-fa)<=.5 and max(abs(dp))<=.125:
                edges.append(dict(previous=i,current=j,frequency_error_hz=float(fb-fa),phase_error_cycles_LR=dp.tolist()))
    for j,line in enumerate(result['lines']):
        line['raw_eligible']=line['eligible']
        cell=proposal['inventory']['bin'][j]
        line['candidate_origin']='propagated' if cell in added else 'native_peak'
        if cell not in added:continue
        keep=[k for k in range(2*m+1) if k not in [j,m+j]]
        null=weighted[:,keep]
        coef,_,rank,_=lstsq(null,target,lapack_driver='gelsd')
        null_residual=null@coef-target
        null_cost=np.sum(null_residual**2,axis=0)
        gain=1-np.divide(full_cost,null_cost,out=np.ones(2),where=null_cost>0)
        matches=[edge for edge in edges if edge['current']==j]
        unique=len(matches)==1 and sum(edge['previous']==matches[0]['previous'] for edge in edges)==1
        predecessor=matches[0]['previous'] if unique else None
        # Compatibility must come from a predecessor that actually proposed
        # this cell, not an unrelated current-wave match discovered afterward.
        proposers=[v['previous_line_index'] for v in proposal['provenance'] if v['state']=='proposed' and v['native_bin']==cell]
        supported=bool(unique and predecessor in proposers and rank==2*m-1 and min(gain)>=.8)
        line['eligible']=bool(line['raw_eligible'] and supported)
        tests.append(dict(index=j,native_bin=cell,conditional_full_cost_LR=full_cost.tolist(),
            conditional_null_cost_LR=null_cost.tolist(),null_rank=int(rank),partial_gain_LR=gain.tolist(),
            compatible_predecessors=[v['previous'] for v in matches],unique_predecessor=predecessor,
            actual_proposers=proposers,current_wave_and_predecessor_supported=supported,accepted=line['eligible']))
    return result,dict(tests=tests,edges=edges,
        conditional_not_fully_nonlinear_absent_optimum=True,statistical_confidence=False)
