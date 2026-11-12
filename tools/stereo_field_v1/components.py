"""Choose PSD frequency detail axes without hiding individual error regressions."""
import numpy as np
from .model import packed,fit


def predict(values,indices,count,prior,axis):
    child,_=fit(values,indices,count,prior)
    if axis=='joint':return child
    parent,_=fit(values,indices,1,0)
    result=child.copy()
    if axis=='cross_only':result[:,:2]=parent[:,:2]
    elif axis=='balance_only':result[:,2:]=parent[:,2:]
    else:raise ValueError('Unknown field axis')
    radius=np.sqrt(result[:,0]*result[:,1]);magnitude=np.hypot(result[:,2],result[:,3])
    scale=np.minimum(1,radius/np.maximum(magnitude,1e-300));result[:,2:]*=scale[:,None]
    if axis=='cross_only':assert np.array_equal(result[:,:2],parent[:,:2])
    return result


def losses(values,indices,prediction):
    sample=values[indices];trace=sample[:,:,0]+sample[:,:,1]
    difference=(sample/np.maximum(trace[:,:,None],1e-300)-prediction)**2
    return np.stack(((trace*difference[:,:,:2].sum(axis=2)).sum(axis=1),
        (2*trace*difference[:,:,2:].sum(axis=2)).sum(axis=1)),axis=-1)


def evaluate(data,plan):
    half=len(data['left'])//2;blocks=len(data['left']);rows=[]
    splits=[('forward',list(range(half)),list(range(blocks-half,blocks))),
        ('reverse',list(range(blocks-half,blocks)),list(range(half)))]
    for low,high in plan['bands']:
        mask=(data['hz']>=low)&(data['hz']<high);value=packed(data,mask);directions=[]
        for name,train,test in splits:
            choices=[dict(subdivisions=1,prior=0,axis='joint')]
            if len(train)>=plan['minimum_training_blocks']:
                choices += [dict(subdivisions=n,prior=p,axis=a) for n in plan['subdivisions'] if n<=value.shape[1]
                    for p in plan['parent_prior_weights'] for a in plan['axes']]
                for candidate in choices:
                    errors=[]
                    for held in train:
                        training=[i for i in train if i!=held]
                        prediction=predict(value,training,candidate['subdivisions'],candidate['prior'],candidate['axis'])
                        errors.extend(losses(value,[held],prediction).sum(axis=1).tolist())
                    candidate['cv_rmse']=float(np.sqrt(np.mean(errors)))
                best=min(choices,key=lambda x:x['cv_rmse']);base_cv=choices[0]['cv_rmse']
                inner_reduction=1-best['cv_rmse']/base_cv if base_cv>plan['minimum_baseline_rmse'] else 0
                selected=best if inner_reduction>=plan['minimum_inner_cv_rmse_reduction'] else choices[0]
            else:selected=choices[0];inner_reduction=0
            base=predict(value,train,1,0,'joint')
            chosen=predict(value,train,selected['subdivisions'],selected['prior'],selected['axis'])
            old=losses(value,test,base).mean(axis=0);new=losses(value,test,chosen).mean(axis=0)
            old_rmse=float(np.sqrt(sum(old)));new_rmse=float(np.sqrt(sum(new)))
            reduction=1-new_rmse/old_rmse if old_rmse>plan['minimum_baseline_rmse'] else 0
            component_ok=bool(np.all(new<=old+plan['component_mse_regression_tolerance']))
            excess=float(np.max(chosen[:,2]**2+chosen[:,3]**2-chosen[:,0]*chosen[:,1]))
            assert excess<plan['tolerances']['PSD_excess'] and np.min(chosen[:,:2])>=0
            qualified=(selected['subdivisions']>1 and reduction>=plan['minimum_test_rmse_reduction']
                and old_rmse-new_rmse>=plan['minimum_absolute_test_rmse_reduction'] and component_ok)
            directions.append(dict(direction=name,train_blocks=train,test_blocks=test,selected=selected,inner_candidates=choices,
                best_inner_reduction=float(inner_reduction),baseline_component_mse=old.tolist(),candidate_component_mse=new.tolist(),
                baseline_test_rmse=old_rmse,candidate_test_rmse=new_rmse,test_rmse_reduction=float(reduction),
                individual_components_nonregressing=component_ok,predictive_gate_passed=bool(qualified),maximum_PSD_excess=excess,
                bin_hz=data['hz'][mask].tolist(),predicted_matrix=chosen.tolist()))
        rows.append(dict(hz=[low,high],frequency_bins=int(mask.sum()),directions=directions,
            bidirectional_gate_passed=all(d['predictive_gate_passed'] for d in directions)))
    return rows
