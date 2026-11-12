"""PSD stereo orientation, common-power invariant, with train-only complexity CV."""
import numpy as np


def packed(data,mask):
    a=data['left'][:,mask];b=data['right'][:,mask];c=data['cross'][:,mask]
    total=(a+b).sum(axis=1)
    if np.any(total<=0):raise ValueError('Band has no observed trace')
    return np.stack((a,b,c.real,c.imag),axis=-1)/total[:,None,None]


def fit(values,indices,subdivisions,prior):
    sample=values[indices]
    aggregate=sample.sum(axis=(0,1));trace=aggregate[0]+aggregate[1]
    parent=aggregate/trace
    prediction=np.empty(values.shape[1:]);cells=[]
    for cell in np.array_split(np.arange(values.shape[1]),subdivisions):
        if not len(cell):raise ValueError('More cells than FFT bins')
        moment=sample[:,cell].sum(axis=(0,1));weight=moment[0]+moment[1]
        pseudo=prior*trace/subdivisions
        value=(moment+pseudo*parent)/(weight+pseudo) if weight+pseudo>0 else parent.copy()
        prediction[cell]=value
        cells.append(dict(bins=cell.tolist(),matrix=value.tolist(),observed_trace=float(weight),prior_trace=float(pseudo)))
    return prediction,cells


def losses(values,indices,prediction):
    sample=values[indices];trace=sample[:,:,0]+sample[:,:,1]
    orientation=sample/np.maximum(trace[:,:,None],1e-300)
    squared=(prediction-orientation)**2
    return (trace*(squared*np.array([1,1,2,2])).sum(axis=-1)).sum(axis=1)


def select(values,indices,plan):
    candidates=[(1,0)]+[(n,p) for n in plan['subdivisions'] for p in plan['parent_prior_weights'] if n<=values.shape[1]]
    rows=[]
    for count,prior in candidates:
        error=[]
        for held in indices:
            training=[i for i in indices if i!=held]
            predicted,_=fit(values,training,count,prior)
            error.extend(losses(values,[held],predicted).tolist())
        rows.append(dict(subdivisions=count,prior=prior,cv_rmse=float(np.sqrt(np.mean(error)))))
    base=rows[0]['cv_rmse'];chosen=min(range(len(rows)),key=lambda i:rows[i]['cv_rmse'])
    reduction=1-rows[chosen]['cv_rmse']/base if base>plan['minimum_baseline_rmse'] else 0
    if reduction<plan['minimum_inner_cv_rmse_reduction']:chosen=0
    return rows[chosen],rows,float(reduction)


def evaluate(data,plan):
    blocks=len(data['left']);half=blocks//2
    splits=[('forward',list(range(half)),list(range(blocks-half,blocks))),
        ('reverse',list(range(blocks-half,blocks)),list(range(half)))]
    records=[]
    for low,high in plan['bands']:
        mask=(data['hz']>=low)&(data['hz']<high);values=packed(data,mask)
        directions=[]
        for name,training,test in splits:
            baseline,_=fit(values,training,1,0)
            if len(training)>=plan['minimum_training_blocks']:
                selected,candidates,inner_reduction=select(values,training,plan)
            else:selected=dict(subdivisions=1,prior=0);candidates=[];inner_reduction=0
            prediction,cells=fit(values,training,selected['subdivisions'],selected['prior'])
            old=float(np.sqrt(np.mean(losses(values,test,baseline))))
            new=float(np.sqrt(np.mean(losses(values,test,prediction))))
            reduction=1-new/old if old>plan['minimum_baseline_rmse'] else 0
            absolute=old-new
            excess=float(np.max(prediction[:,2]**2+prediction[:,3]**2-prediction[:,0]*prediction[:,1]))
            assert excess<plan['tolerances']['PSD_excess'] and np.min(prediction[:,:2])>=0
            qualifies=(bool(candidates) and selected['subdivisions']>1 and reduction>=plan['minimum_test_rmse_reduction']
                and absolute>=plan['minimum_absolute_test_rmse_reduction'])
            directions.append(dict(direction=name,train_blocks=training,test_blocks=test,
                enough_training_blocks=bool(candidates),selected=selected,inner_candidates=candidates,
                best_inner_reduction=inner_reduction,baseline_test_rmse=old,candidate_test_rmse=new,
                test_rmse_reduction=float(reduction),absolute_test_rmse_reduction=absolute,
                predictive_gate_passed=bool(qualifies),maximum_PSD_excess=excess,
                bin_hz=data['hz'][mask].tolist(),cells=cells))
        records.append(dict(hz=[low,high],frequency_bins=int(mask.sum()),directions=directions,
            bidirectional_gate_passed=all(row['predictive_gate_passed'] for row in directions)))
    return records
