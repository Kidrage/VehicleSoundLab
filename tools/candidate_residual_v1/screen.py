"""Pre-insertion conditional linear support for observed cubic forecasts."""
import copy
import numpy as np
from scipy.linalg import lstsq
from native_phase_patch_v1.basis import geometry


def select(native,arrays,audio,proposal,previous,plan):
    output=copy.deepcopy(proposal)
    report=dict(tests=[],full_rank=None,full_cost_LR=None,
        global_conditional_linear_not_nonlinear_or_statistical=True)
    if not proposal['added_bins']:
        report['reason']='no_added_candidate'
        return output,report,{}
    m=len(native['lines'])
    if not m or m+len(proposal['added_bins'])>plan['maximum_modes']:
        report['reason']='empty_or_overflow_whole_hypothesis'
        return None,report,{}
    predecessors=previous.get('lines',[]) if previous else []
    forecasts=[]
    for cell in proposal['added_bins']:
        parents=[v['previous_line_index'] for v in proposal['provenance'] if v['state']=='proposed' and v['native_bin']==cell]
        test=dict(native_bin=cell,proposers=parents,passed=False)
        if len(parents)!=1:
            test['reason']='ambiguous_predecessors'
        else:
            line=predecessors[parents[0]]
            q,a=line['chirp_hz_per_second'],line['curvature_hz_per_second2']
            f=line['frequency_hz']+.25*q+.03125*a
            q=q+.25*a
            test.update(forecast_frequency_hz=f,forecast_rate_hzs=q,forecast_curvature_hzs2=a,
                forecast_edge_rates_hzs=[q-.125*a,q+.125*a])
            if max(abs(q-.125*a),abs(q+.125*a))>plan['maximum_chirp_hz_per_second']:
                test['reason']='forecast_rate_outside_original_box'
            else:
                forecasts.append((cell,f,q,a,test))
        report['tests'].append(test)
    if forecasts:
        n=len(audio)
        t=np.arange(n)/plan['sample_rate']-.125
        w=np.sqrt((.5-.5*np.cos(2*np.pi*np.arange(n)/n))/n)
        base=2*np.pi*t[:,None]*arrays['nominal']+geometry(t,.25)@arrays['parameters'].reshape(3,m)
        extra=np.column_stack([2*np.pi*(f*t+.5*q*t*t+a*t**3/6) for _,f,q,a,_ in forecasts])
        angles=np.column_stack((base,extra))
        total=angles.shape[1]
        design=np.column_stack((np.cos(angles),np.sin(angles),np.ones(n)))
        matrix=w[:,None]*design
        target=w[:,None]*audio
        full,_,rank,_=lstsq(matrix,target,lapack_driver='gelsy')
        residual=matrix@full-target
        full_cost=np.sum(residual**2,axis=0)
        power=.5*np.mean(full[:total]**2+full[total:2*total]**2,axis=1)
        floor=max(power)*10**(plan['minimum_line_power_db_relative_to_maximum']/10)
        report.update(full_rank=int(rank),full_cost_LR=full_cost.tolist(),power_floor=float(floor),
            native_modes=m,screen_modes=total)
        saved=dict(forecast_parameters=np.array([[f,q,a] for _,f,q,a,_ in forecasts]),
            forecast_bins=np.array([cell for cell,_,_,_,_ in forecasts]),coefficients=full)
        for k,(cell,_,_,_,test) in enumerate(forecasts):
            index=m+k
            columns=[j for j in range(2*total+1) if j not in [index,index+total]]
            null=matrix[:,columns]
            co,_,null_rank,_=lstsq(null,target,lapack_driver='gelsy')
            null_cost=np.sum((null@co-target)**2,axis=0)
            gain=1-np.divide(full_cost,null_cost,out=np.ones(2),where=null_cost>0)
            supported=bool(native['success'] and rank==2*total+1 and null_rank==2*total-1
                and power[index]>0 and power[index]>=floor and min(gain)>=plan['minimum_local_explained_fraction'])
            test.update(reason='supported' if supported else 'insufficient_conditional_support',
                full_cost_LR=full_cost.tolist(),null_cost_LR=null_cost.tolist(),null_rank=int(null_rank),
                partial_gain_LR=gain.tolist(),power=float(power[index]),relative_power_ok=bool(power[index]>=floor),passed=supported)
            saved['null_coefficients_'+str(cell)]=co
    else:
        saved={}
        report['reason']='all_forecasts_ambiguous_or_outside_box'
    passed={v['native_bin'] for v in report['tests'] if v['passed']}
    rejected=set(proposal['added_bins'])-passed
    output['added_bins']=sorted(passed)
    keep=[i for i,cell in enumerate(proposal['inventory']['bin']) if cell not in rejected]
    output['inventory']={key:[values[i] for i in keep] for key,values in proposal['inventory'].items()}
    output['initial_chirp']=[proposal['initial_chirp'][i] for i in keep]
    for value in output['provenance']:
        if value['state']=='proposed' and value['native_bin'] in rejected:value['state']='residual_screen_rejected'
    return output,report,saved
