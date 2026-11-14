"""Independent trig/window, QR and all signed cross-covariance evidence audit."""
import argparse,csv,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import linalg
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',new_phase_observer_qualified=False,physical_AM_PM_identified=False)
def circular(z,starts):
    theta=np.angle(z);psi=theta[:,2]-theta[:,1]-theta[:,0];eta=3*theta[:,0]-2*theta[:,1]
    v=np.column_stack((np.cos(psi),np.cos(eta),np.sin(psi),np.sin(eta)))
    w=.5*(1-np.cos(2*np.pi*np.arange(9600)/9600))
    return np.array([w@v[first:first+9600]/math.fsum(w) for first in starts])

def qr(x,y):
    mean=np.array([math.fsum(x[:,j])/len(x) for j in range(4)])
    std=np.array([math.sqrt(math.fsum((x[:,j]-mean[j])**2)/len(x)) for j in range(4)])
    A=np.column_stack((np.ones(len(x)),(x-mean)/std))
    q,u=linalg.qr(A,mode='economic');b=linalg.solve_triangular(u,q.T@y)
    return mean,std,b,np.linalg.cond(A)

try:
    observed=load(a.input/'report.json');assert observed['result']=='frozen_AM_relative_phase_relationship_observed'
    for path,digest in observed['inputs'].items():assert sha(path)==digest
    for path,digest in observed['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    r['input_sha256']=sha(a.input/'report.json')
    errors=dict(all_window_trig=0.,all_targets=0.,all51x7x7covariance=0.,all_QR_beta=0.,
        all_predictions=0.,all_metrics=0.,all_feature_summaries=0.)
    data={}
    for row in observed['cases']:
        assert sha(a.input/row['file'])==row['sha256'] and sha(row['input'])==row['input_sha256']
        with np.load(row['input']) as source:
            starts=source['starts'];x=circular(source['phasors'],starts)
            y=np.column_stack([np.log(abs(source['local_coefficients'][:,j])) for j in [1,2,4]])
        assert np.array_equal(starts,np.arange(12000,122401,960))
        with np.load(a.input/row['file']) as saved:
            errors['all_window_trig']=max(errors['all_window_trig'],float(abs(x-saved['x']).max()))
            errors['all_targets']=max(errors['all_targets'],float(abs(y-saved['y']).max()))
            raw=np.column_stack((y,x));v=raw-raw.mean(axis=0);curve=[]
            for lag in range(-25,26):
                origins=range(max(0,-lag),min(len(v),len(v)-lag))
                curve.append([[math.fsum(float(v[i,j])*float(v[i+lag,k]) for i in origins)/len(origins)
                    for k in range(7)] for j in range(7)])
            curve=np.array(curve)
            assert np.array_equal(saved['overlap_counts'],116-abs(np.arange(-25,26)))
            errors['all51x7x7covariance']=max(errors['all51x7x7covariance'],float(abs(curve-saved['covariance']).max()))
            for field,oracle in [('x_mean',x.mean(axis=0)),('x_std',x.std(axis=0)),
                ('log_magnitude_mean',y.mean(axis=0)),('log_magnitude_std',y.std(axis=0))]:
                errors['all_feature_summaries']=max(errors['all_feature_summaries'],float(abs(oracle-row[field]).max()))
        data[row['label']]=(x,y,curve)
    assert len(data)==8
    fitted={}
    for family,model in observed['models'].items():
        x,y,_=data[family+'_train'];mean,std,b,condition=qr(x,y)
        assert model['available'] and model['rank']==5 and condition<=1e6
        errors['all_QR_beta']=max(errors['all_QR_beta'],float(abs(b-model['coefficients']).max()),
            float(abs(mean-model['mean']).max()),float(abs(std-model['std']).max()),abs(condition-model['condition']))
        fitted[family]=(mean,std,b)
    for row in observed['evaluations']:
        family=row['family'];x,y,_=data[family+'_'+row['part']];mean,std,b=fitted[family]
        pred=np.column_stack((np.ones(len(x)),(x-mean)/std))@b
        assert sha(a.input/row['prediction_file'])==row['prediction_sha256']
        errors['all_predictions']=max(errors['all_predictions'],float(abs(pred-np.load(a.input/row['prediction_file'])).max()))
        base=data[family+'_train'][1].mean(axis=0)
        mse=np.array([math.fsum((pred[:,j]-y[:,j])**2)/len(y) for j in range(3)])
        reference=np.array([math.fsum((base[j]-y[:,j])**2)/len(y) for j in range(3)])
        for key,value in [('MSE',mse),('TRAIN_constant_MSE',reference),('fractional_MSE_reduction',1-mse/reference)]:
            errors['all_metrics']=max(errors['all_metrics'],float(abs(value-row[key]).max()))
    mean,std,b=fitted['source'];base=data['source_train'][1].mean(axis=0)
    for row in observed['source_model_to_phase_controls']:
        x,y,_=data[row['label']];pred=np.column_stack((np.ones(len(x)),(x-mean)/std))@b
        mse=np.mean((pred-y)**2,axis=0);ref=np.mean((base-y)**2,axis=0)
        for key,value in [('MSE',mse),('TRAIN_constant_MSE',ref),('fractional_MSE_reduction',1-mse/ref)]:
            errors['all_metrics']=max(errors['all_metrics'],float(abs(value-row[key]).max()))
    scale=np.column_stack((data['source_train'][1],data['source_train'][0])).std(axis=0)
    assert abs(scale-observed['source_TRAIN_covariance_scale']).max()<1e-12
    for label,(_,_,c) in data.items():
        maximum=abs(c[:,:3,3:]/scale[:3,None]/scale[None,3:]).max()
        errors['all_metrics']=max(errors['all_metrics'],abs(float(maximum)-observed['all51lag_maximum_scaled_AM_phase_covariance'][label]))
    # Independent analytic fixtures and their exact stored predictions.
    with np.load(a.input/'known.npz') as known:
        assert abs(circular(known['phasors'],known['starts'])-known['expected_features']).max()<1e-12
        t=np.arange(232)/50
        x=np.column_stack((np.sin(2*np.pi*.8*t+.2),np.cos(2*np.pi*1.3*t-.1),np.cos(2*np.pi*.8*t+.2),np.sin(2*np.pi*1.3*t-.1)))
        beta=np.array([[.12,-.08,.03],[.02,.11,-.06],[-.04,.02,.09],[.07,-.03,.02]])
        y=np.array([-2.2,-2.3,-3.1])+x@beta
        for name,v in [('train_x',x[:116]),('check_x',x[116:]),('train_y',y[:116]),('check_y',y[116:])]:assert abs(v-known[name]).max()<1e-12
        mu,sd,b,_=qr(x[:116],y[:116]);assert abs(b[1:]/sd[:,None]-beta).max()<1e-12
        assert abs(np.column_stack((np.ones(116),(x[116:]-mu)/sd))@b-y[116:]).max()<1e-12
    old=a.workspace/'baselines/idle_phase_amplitude_v1/evidence/observe1/known.npz'
    with np.load(old) as f:
        for row in observed['frozen_observer_controls']:
            label=row['label'];assert sha(a.input/row['file'])==row['sha256']
            z=f['neighbor_phasors' if label=='neighbor' else label+'_phasors']
            x=circular(z,np.arange(12000,122401,960));y=np.log(abs(f[label+'_coefficients'][:,[1,2,4]]))
            with np.load(a.input/row['file']) as saved:
                assert abs(x-saved['x']).max()<1e-12 and abs(y-saved['y']).max()<1e-12
            assert abs(y.std(axis=0)-row['observed_log_std']).max()<1e-12
    assert max(errors.values())<1e-10,errors
    ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
    assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
    voices=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json')
    assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
    r.update(result='passed',all8source_control_arrays=True,all4TRAIN_QR_and8predictions=True,
        all8x51x7x7raw_covariance_scalar_checked=True,all6source_to_control_transfer_checked=True,
        errors=errors,old619C_H_and67voices_exact=True,new_audio_generated=False,
        note='New feature/regression/statistics independently audited; frozen acoustic projection coefficients reused, not physically validated again.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],errors=r.get('errors')),flush=True)
