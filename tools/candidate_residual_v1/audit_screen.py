"""Independent physical-coordinate/SVD reconstruction of pre-insertion screening."""
import copy
import math
import numpy as np
from scipy.linalg import lstsq
from native_chirp_audit_v1.wave import near


def check(native,nz,audio,candidate,previous,screen,sz,reduced,plan):
    if not candidate['added_bins']:
        assert candidate==reduced and screen['reason']=='no_added_candidate' and not screen['tests'] and not sz.files
        return dict(tests=0,cost_error=0.,gain_error=0.,coefficient_error=0.)
    m=len(native['lines'])
    assert 0<m<=64 and m+len(candidate['added_bins'])<=64
    records=[]
    valid=[]
    for cell in candidate['added_bins']:
        parents=[v['previous_line_index'] for v in candidate['provenance'] if v['state']=='proposed' and v['native_bin']==cell]
        record=dict(native_bin=cell,proposers=parents)
        if len(parents)!=1:record['reason']='ambiguous_predecessors'
        else:
            line=previous['lines'][parents[0]]
            assert line['eligible']
            f=line['frequency_hz']+(line['chirp_hz_per_second']+line['curvature_hz_per_second2']/8)/4
            q=line['chirp_hz_per_second']+line['curvature_hz_per_second2']/4
            a=line['curvature_hz_per_second2']
            record.update(forecast_frequency_hz=f,forecast_rate_hzs=q,forecast_curvature_hzs2=a,
                forecast_edge_rates_hzs=[q-a/8,q+a/8])
            if max(abs(q-a/8),abs(q+a/8))>500:record['reason']='forecast_rate_outside_original_box'
            else:valid.append(record)
        records.append(record)
    cost_error=gain_error=coefficient_error=0.
    n=len(audio)
    t=np.array([(i-6000)/48000 for i in range(n)])
    w=np.sqrt(np.hanning(n+1)[:-1]/n)
    if valid:
        native_params=[[v['frequency_hz'],v['chirp_hz_per_second'],v['curvature_hz_per_second2']] for v in native['lines']]
        params=np.array(native_params+[[v['forecast_frequency_hz'],v['forecast_rate_hzs'],v['forecast_curvature_hzs2']] for v in valid])
        M=len(params)
        carriers=np.exp(1j*math.tau*(t[:,None]*params[:,0]+t[:,None]**2*params[:,1]/2+t[:,None]**3*params[:,2]/6))
        design=np.column_stack((carriers.real,carriers.imag,np.ones(n)))
        matrix=w[:,None]*design
        target=w[:,None]*audio
        coefficients,_,rank,_=lstsq(matrix,target,lapack_driver='gelsd')
        coefficient_error=near(coefficients,sz['coefficients'],1e-10)
        full_cost=np.array([math.fsum(row*row) for row in (matrix@coefficients-target).T])
        near(params[m:],sz['forecast_parameters'])
        assert [v['native_bin'] for v in valid]==sz['forecast_bins'].tolist()
        assert screen['native_modes']==m and screen['screen_modes']==M and screen['full_rank']==rank
        cost_error=max(cost_error,near(full_cost,screen['full_cost_LR'],1e-12))
        power=[sum(coefficients[k]**2+coefficients[k+M]**2)/4 for k in range(M)]
        floor=max(power)*10**(-42/10)
        near(floor,screen['power_floor'])
        for k,record in enumerate(valid):
            j=m+k
            columns=[v for v in range(2*M+1) if v!=j and v!=M+j]
            null=matrix[:,columns]
            coef,_,null_rank,_=lstsq(null,target,lapack_driver='gelsd')
            coefficient_error=max(coefficient_error,near(coef,sz['null_coefficients_'+str(record['native_bin'])],1e-10))
            null_cost=np.array([math.fsum(row*row) for row in (null@coef-target).T])
            gain=[1-f/c if c>0 else 0. for f,c in zip(full_cost,null_cost)]
            supported=bool(native['success'] and rank==2*M+1 and null_rank==2*M-1 and power[j]>0 and power[j]>=floor and min(gain)>=.8)
            record.update(passed=supported,reason='supported' if supported else 'insufficient_conditional_support',
                full_cost_LR=full_cost.tolist(),null_cost_LR=null_cost.tolist(),null_rank=int(null_rank),
                partial_gain_LR=gain,power=float(power[j]),relative_power_ok=bool(power[j]>=floor))
    for record,stored in zip(records,screen['tests']):
        record.setdefault('passed',False)
        assert record.keys()==stored.keys()
        for key in record:
            if key in ['full_cost_LR','null_cost_LR']:cost_error=max(cost_error,near(record[key],stored[key],1e-12))
            elif key=='partial_gain_LR':gain_error=max(gain_error,near(record[key],stored[key],1e-8))
            elif key in ['forecast_frequency_hz','forecast_rate_hzs','forecast_curvature_hzs2','forecast_edge_rates_hzs','power']:near(record[key],stored[key])
            else:assert record[key]==stored[key]
    assert len(records)==len(screen['tests']) and screen['global_conditional_linear_not_nonlinear_or_statistical']
    passed={v['native_bin'] for v in records if v['passed']}
    rejected=set(candidate['added_bins'])-passed
    expected=copy.deepcopy(candidate)
    expected['added_bins']=sorted(passed)
    keep=[k for k,cell in enumerate(candidate['inventory']['bin']) if cell not in rejected]
    expected['inventory']={key:[values[k] for k in keep] for key,values in candidate['inventory'].items()}
    expected['initial_chirp']=[candidate['initial_chirp'][k] for k in keep]
    for v in expected['provenance']:
        if v['state']=='proposed' and v['native_bin'] in rejected:v['state']='residual_screen_rejected'
    assert expected==reduced
    return dict(tests=len(records),cost_error=cost_error,gain_error=gain_error,coefficient_error=coefficient_error)
