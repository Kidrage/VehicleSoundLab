"""Independent scalar proposals/edges and QR conditional-null reconstruction."""
import math
import numpy as np
from scipy.linalg import lstsq
from native_chirp_audit_v1.wave import near


def proposal(inv,initial,previous,saved):
    detected=list(inv['bin'])
    candidates={}
    records=[]
    for k,line in enumerate(previous['lines'] if previous else []):
        if not line['eligible']:continue
        center=line['frequency_hz']+.25*line['chirp_hz_per_second']+.03125*line['curvature_hz_per_second2']
        rate=line['chirp_hz_per_second']+.25*line['curvature_hz_per_second2']
        cell=round(center/4)
        state='out_of_domain' if not 30<=cell*4<7000 else 'already_detected' if cell in detected else (
            'ambiguous_near_detected' if min([abs(cell-j) for j in detected],default=math.inf)<2 else 'proposed')
        value=dict(previous_line_index=k,predicted_frequency_hz=center,predicted_rate_hzs=rate,native_bin=cell,state=state)
        records.append(value)
        if state=='proposed':candidates.setdefault(cell,[]).append(value)
    conflicts=[j for j in candidates if any(k!=j and abs(k-j)<2 for k in candidates)]
    added=sorted(set(candidates)-set(conflicts))
    for value in records:
        if value['state']=='proposed' and value['native_bin'] in conflicts:value['state']='ambiguous_between_proposals'
    cells=sorted(set(detected)|set(added))
    assert cells==saved['inventory']['bin'] and added==saved['added_bins']
    assert saved['minimum_cell_spacing']==2 and saved['truth_or_future_input'] is False
    assert len(records)==len(saved['provenance'])
    for left,right in zip(records,saved['provenance']):
        assert left.keys()==right.keys()
        for key in left:
            if key in ['predicted_frequency_hz','predicted_rate_hzs']:near(left[key],right[key])
            else:assert left[key]==right[key]
    frequencies=[]
    rates=[]
    for cell in cells:
        if cell in detected:
            k=detected.index(cell)
            frequencies.append(inv['hz'][k])
            rates.append(initial['initial_chirp'][k])
        else:
            frequencies.append(cell*4.)
            rates.append(math.fsum(v['predicted_rate_hzs'] for v in candidates[cell])/len(candidates[cell]))
    near(frequencies,saved['inventory']['hz'])
    near(rates,saved['initial_chirp'])


def at(line,t):
    f,q,c=[line[k] for k in ['frequency_hz','chirp_hz_per_second','curvature_hz_per_second2']]
    return f+q*t+c*t*t/2,[p/math.tau+f*t+q*t*t/2+c*t**3/6 for p in line['phase_at_midpoint_LR']]


def presence(z,raw,accepted,prop,previous,saved):
    assert raw.keys()==accepted.keys()
    for key in raw:
        if key!='lines':assert raw[key]==accepted[key]
    if not raw['lines']:
        assert accepted==raw and saved['tests']==saved['edges']==[]
        return dict(tests=0,maximum_cost_error=0.,maximum_gain_error=0.)
    m=len(raw['lines'])
    t=(np.arange(12000)-6000)/48000
    f=np.array([v['frequency_hz'] for v in raw['lines']])
    q=np.array([v['chirp_hz_per_second'] for v in raw['lines']])
    c=np.array([v['curvature_hz_per_second2'] for v in raw['lines']])
    carrier=np.exp(1j*math.tau*(t[:,None]*f+t[:,None]**2*q/2+t[:,None]**3*c/6))
    w=np.sqrt(np.hanning(12001)[:-1]/12000)
    matrix=w[:,None]*np.column_stack((carrier.real,carrier.imag,np.ones(12000)))
    target=w[:,None]*z['audio']
    # Independently re-solve the full linear problem as well as every null.
    full=lstsq(matrix,target,lapack_driver='gelsy')[0]
    full_cost=np.array([math.fsum(v*v) for v in (matrix@full-target).T])
    edges=[]
    for i,a in enumerate(previous['lines'] if previous else []):
        if not a['eligible']:continue
        fa,pa=at(a,.125)
        for j,b in enumerate(raw['lines']):
            if not b['eligible']:continue
            fb,pb=at(b,-.125)
            error=[(y-x+.5)%1-.5 for x,y in zip(pa,pb)]
            if abs(fb-fa)<=.5 and max(map(abs,error))<=.125:
                edges.append(dict(previous=i,current=j,frequency_error_hz=fb-fa,phase_error_cycles_LR=error))
    assert len(edges)==len(saved['edges'])
    for x,y in zip(edges,saved['edges']):
        assert (x['previous'],x['current'])==(y['previous'],y['current'])
        near(x['frequency_error_hz'],y['frequency_error_hz'])
        near(x['phase_error_cycles_LR'],y['phase_error_cycles_LR'])
    count=0
    cost_error=gain_error=0.
    for j,(line,value) in enumerate(zip(raw['lines'],accepted['lines'])):
        cell=prop['inventory']['bin'][j]
        added=cell in prop['added_bins']
        assert value.keys()==line.keys()|{'raw_eligible','candidate_origin'}
        for key in line:
            if key!='eligible':assert value[key]==line[key]
        assert value['raw_eligible']==line['eligible']
        assert value['candidate_origin']==('propagated' if added else 'native_peak')
        if not added:
            assert value['eligible']==line['eligible']
            continue
        test=saved['tests'][count]
        count+=1
        assert (test['index'],test['native_bin'])==(j,cell)
        columns=[k for k in range(2*m+1) if k!=j and k!=j+m]
        null=matrix[:,columns]
        co,_,rank,_=lstsq(null,target,lapack_driver='gelsy')
        null_cost=np.array([math.fsum(v*v) for v in (null@co-target).T])
        gains=[1-x/y if y>0 else 0. for x,y in zip(full_cost,null_cost)]
        cost_error=max(cost_error,near(full_cost,test['conditional_full_cost_LR'],1e-12),
                       near(null_cost,test['conditional_null_cost_LR'],1e-12))
        gain_error=max(gain_error,near(gains,test['partial_gain_LR'],1e-8))
        predecessors=[edge['previous'] for edge in edges if edge['current']==j]
        unique=len(predecessors)==1 and sum(edge['previous']==predecessors[0] for edge in edges)==1
        identity=predecessors[0] if unique else None
        proposers=[v['previous_line_index'] for v in prop['provenance'] if v['state']=='proposed' and v['native_bin']==cell]
        supported=bool(unique and identity in proposers and rank==2*m-1 and min(gains)>=.8)
        assert rank==test['null_rank'] and predecessors==test['compatible_predecessors']
        assert identity==test['unique_predecessor'] and proposers==test['actual_proposers']
        assert supported==test['current_wave_and_predecessor_supported']
        assert value['eligible']==test['accepted']==bool(line['eligible'] and supported)
    assert count==len(saved['tests'])
    assert saved['conditional_not_fully_nonlinear_absent_optimum'] and saved['statistical_confidence'] is False
    return dict(tests=count,maximum_cost_error=cost_error,maximum_gain_error=gain_error)
