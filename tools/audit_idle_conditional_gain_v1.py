"""Independent native/QR audit of conditional means, not hidden-source inference."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','diagnosis','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.linalg import solve_triangular
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},cases=[],QR_factorizations=0)
source=load(a.input/'report.json');assert source['result']=='native_conditional_mean_fitted_pending_audit'
diagnosis=load(a.diagnosis/'report.json');assert diagnosis['result']=='rejected_source_fixed_diagnosis'
assert diagnosis['input_sha256']==r['input_sha256'] and not diagnosis['refit']
r['diagnosis_sha256']=sha(a.diagnosis/'report.json')
S=[1,2,4];starts=np.arange(12000,122401,960);frames=9600
weight=.5-.5*np.cos(2*np.pi*np.arange(frames)/frames);sqrtw=np.sqrt(weight)


def error(key,x,y,tolerance):
    d=float(np.max(np.abs(np.asarray(x)-np.asarray(y))))
    r['errors'][key]=max(r['errors'].get(key,0.),d)
    assert d<=tolerance,(key,d,tolerance)


def native_features(z):
    angle=np.angle(z);psi=angle[:,2]-angle[:,1]-angle[:,0];eta=3*angle[:,0]-2*angle[:,1]
    return np.stack((np.cos(psi),np.cos(eta),np.sin(psi),np.sin(eta)),axis=1)


def gain(parameters,x):
    p=np.array(parameters).reshape(2,5)
    out=np.ones((len(x),3))
    for m in range(2):out[:,m]=np.exp(p[m,0]+sum(p[m,k+1]*x[:,k] for k in range(4)))
    return out


def projection(f):
    z=f['phasors'];freq=f['frequencies'];beta=f['beta']
    t=np.arange(len(z))/48000
    A=np.empty((len(z),27));A[:,-1]=1
    for j,hz in enumerate(freq):
        value=z[:,S.index(j)] if j in S else np.exp(2j*np.pi*hz*t)
        A[:,j]=value.real;A[:,13+j]=value.imag
    baseline=A@beta;c=beta[:13]-1j*beta[13:26]
    real=np.column_stack([np.real(z[:,j]*c[S[j]]) for j in range(3)])
    operators=[];responses=[];constant=[]
    for first in starts:
        slab=A[first:first+frames];q,rr=np.linalg.qr(slab*sqrtw[:,None],mode='reduced')
        rows=solve_triangular(rr,q.T*sqrtw)
        P=rows[S]-1j*rows[np.array(S)+13]
        constant.append(P@baseline[first:first+frames]);operators.append(P)
        responses.append(P[:,:,None]*real[first:first+frames,:2][None,:,:])
        r['QR_factorizations']+=1
    return np.array(operators),np.array(responses),np.array(constant),baseline,real


def apply(cache,g):
    windows=np.stack([g[first:first+frames,:2]-1 for first in starts])
    return cache[2]+np.einsum('wjtm,wtm->wj',cache[1],windows,optimize=True)


def direct(cache,wave):
    return np.array([P@wave[first:first+frames] for first,P in zip(starts,cache[0])])


def scalar_metrics(target,prediction):
    output={key:[] for key in ['complex_MSE','complex_bias_squared','complex_error_variance','log_magnitude_MSE','log_magnitude_error_variance']}
    for m in range(3):
        e=prediction[:,m]-target[:,m];bias=sum(e)/len(e)
        le=np.log(np.abs(prediction[:,m]))-np.log(np.abs(target[:,m]));lmean=sum(le)/len(le)
        output['complex_MSE'].append(sum(abs(v)**2 for v in e)/len(e))
        output['complex_bias_squared'].append(abs(bias)**2)
        output['complex_error_variance'].append(sum(abs(v-bias)**2 for v in e)/len(e))
        output['log_magnitude_MSE'].append(sum(v*v for v in le)/len(le))
        output['log_magnitude_error_variance'].append(sum((v-lmean)**2 for v in le)/len(le))
    return output


def covariance(error_value):
    v=np.column_stack((error_value[:,:2].real,error_value[:,:2].imag));v-=v.mean(axis=0)
    out=np.empty((51,4,4))
    for l,lag in enumerate(range(-25,26)):
        for i in range(4):
            for j in range(4):
                pairs=range(max(0,-lag),min(len(v),len(v)-lag))
                out[l,i,j]=sum(v[k,i]*v[k+lag,j] for k in pairs)/len(pairs)
    return out


def audit_trace(model,cache,x,target,known=False):
    if not model.get('parameters'):return
    for row in model['trace']:
        pred=apply(cache,gain(row['parameters'],x));e=(pred[:,:2]-target[:,:2])/model['TRAIN_scale']
        cost=float(np.sum(e.real**2+e.imag**2));error('all_trace_costs',cost,row['squared_error'],1e-9)
    pred=apply(cache,gain(model['parameters'],x));p=np.array(model['parameters']).reshape(2,5)
    one=np.column_stack((np.ones(len(x)),x));columns=[]
    for m in range(2):
        for k in range(5):
            change=np.zeros((len(x),3));change[:,m]=gain(model['parameters'],x)[:,m]*one[:,k]
            windows=np.stack([change[first:first+frames,:2] for first in starts])
            columns.append(np.einsum('wjtm,wtm->wj',cache[1],windows,optimize=True))
    J=np.stack(columns,axis=-1)[:,:2,:]/np.asarray(model['TRAIN_scale'])[None,:,None]
    active=[0,5] if model['constant'] else np.arange(10)
    J=np.concatenate((J.real.reshape(-1,10),J.imag.reshape(-1,10)))[:,active]
    singular=np.linalg.svd(J,compute_uv=False)
    error('all_singular_values',singular,model['singular_values'],1e-9)
    error('all_Jacobian_conditions',singular[0]/singular[-1],model['condition'],1e-7)
    bound=np.abs(p[:,1:]).sum(axis=1);mid=p[:,0]-p[:,1:]@np.asarray(model['center'])
    error('all_global_bounds',np.exp(np.column_stack((mid-bound,mid+bound))),model['global_circular_gain_bounds'],1e-11)


try:
    for path,digest in source['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    for path,digest in source['inputs'].items():assert sha(path)==digest
    failed=load(a.input.parent/'run1/report.json');assert failed['result']=='failed' and 'row_stack' in failed['error']
    original=(a.input.parent/'run1/exact_sources/tools/idle_conditional_gain_v1/model.py').read_text(encoding='utf-8')
    corrected=(a.input/'exact_sources/tools/idle_conditional_gain_v1/model.py').read_text(encoding='utf-8')
    assert original.replace('np.row_stack(', 'np.vstack(')==corrected
    # Known training and all five fixed-parameter prediction portions.
    known_rows=[dict(label='known_train',**source['known']['training_arrays'])]+[
        dict(label=f"known_{v['seed']}_{v['part']}",**v) for v in source['known']['predictions']]
    train_center=None
    for row in known_rows:
        file=a.input/row['file'];assert sha(file)==row['sha256']
        with np.load(file) as n:f={k:n[k] for k in n.files}
        x=native_features(f['phasors'])-f['center'];cache=projection(f)
        if row['label']=='known_train':
            error('known_TRAIN_center',(x+f['center'])[12000:-12000].mean(axis=0),f['center'],1e-12)
            train_center=f['center'];p=f['truth'];expected=f['target']
            error('known_parameter_recovery',source['known']['conditional']['parameters'],f['truth'],1e-5)
            for key in ['constant','conditional']:audit_trace(source['known'][key],cache,x,f['target'],True)
        else:
            error('known_fixed_center',f['center'],train_center,0)
            p=source['known']['conditional']['parameters'];expected=f['prediction']
        g=gain(p,x);wave=cache[3]+np.sum(cache[4]*(g-1),axis=1)
        error('all_mean_waveforms',wave,f['mean_audio'],1e-10)
        error('all_QR_coefficients',direct(cache,wave),expected,1e-10)
        error('all_QR_cached_response',apply(cache,g),expected,1e-10)
        r['cases'].append(dict(label=row['label'],windows=116));save(a.out/'report.json',r)
        print(dict(audited=row['label']),flush=True);del cache
    marginal=np.asarray(source['known']['hidden_innovation_marginal_mean']);error('hidden_mean_only_quadrature',marginal,[1.,1.],1e-12)
    # All real source/control rows, full native waves and independent QR.
    for row in source['evaluations']+diagnosis['cases']:
        folder=a.diagnosis if row['family']=='source' else a.input
        file=folder/row['file'];assert sha(file)==row['sha256']
        with np.load(file) as n:f={k:n[k] for k in n.files}
        family=row['family'];model=source['models'][family];part=row['part']
        original=Path(model['source_file']).with_name(family+'_'+part+'.npz')
        with np.load(original) as n:
            error('original_phasors',f['phasors'],n['phasors'],0)
            error('original_window_targets',f['target'],n['local_coefficients'][:,S],0)
            if part=='train':error('TRAIN_fixed_coefficients',f['beta'],n['global_coefficients'][:,0],0)
        error('all_FIXED_TRAIN_beta',f['beta'],model['TRAIN_beta'],0)
        x=native_features(f['phasors'])-f['center'];cache=projection(f)
        if part=='train':error('all_TRAIN_centers',(x+f['center'])[12000:-12000].mean(axis=0),f['center'],1e-12)
        else:error('CHECK_no_recentering',f['center'],model['conditional']['center'],0)
        computed={}
        for key in ['constant','conditional']:
            p=model[key]['parameters'];g=gain(p,x)
            wave=cache[3]+np.sum(cache[4]*(g-1),axis=1)
            error('all_native_gains',g,f[key+'_gain'],1e-11)
            error('all_mean_waveforms',wave,f[key+'_audio'],1e-10)
            predicted=direct(cache,wave)
            error('all_QR_coefficients',predicted,f[key+'_prediction'],1e-10)
            error('all_QR_cached_response',apply(cache,g),predicted,1e-10)
            computed[key]=scalar_metrics(f['target'],predicted)
            for name,values in computed[key].items():error('all_metrics',values,row['metrics'][key][name],1e-10)
            if row['family']=='source':
                e=predicted-f['target']
                error('all_real_imag_MSE',np.mean(e.real**2,axis=0),row['metrics'][key]['real_MSE'],1e-11)
                error('all_real_imag_MSE',np.mean(e.imag**2,axis=0),row['metrics'][key]['imag_MSE'],1e-11)
                error('all_source_gain_ranges',np.column_stack((g.min(axis=0),g.max(axis=0))),row['native_gain_range'][key],1e-11)
                inside=g[12000:-12000]
                error('all_source_gain_ranges',np.column_stack((inside.min(axis=0),inside.max(axis=0))),row['interior_gain_range'][key],1e-11)
            if part=='train':audit_trace(model[key],cache,x,f['target'])
        b=np.asarray(computed['constant']['complex_MSE']);n=np.asarray(computed['conditional']['complex_MSE'])
        error('all_complex_MSE_reductions',1-n/b,row['fractional_complex_MSE_reduction'],1e-8)
        curves=covariance(f['conditional_prediction']-f['target'])
        error('all_signed_residual_covariances',curves,f['error_covariance_signed_lags'],1e-12)
        if part=='train' and row['family']!='source':error('all_descriptive_uncertainty',curves[25],row['descriptive_uncertainty']['real_imag_covariance'],1e-12)
        r['cases'].append(dict(label=family+'_'+part,windows=116));save(a.out/'report.json',r)
        print(dict(audited=family+'_'+part),flush=True);del cache
    assert len(r['cases'])==14 and r['QR_factorizations']==1624
    assert not source['models']['source']['conditional']['available']
    r.update(result='passed',scope='Native conditional mean and descriptive observation residual only; no identified hidden variance or real joint source',
        original_failed_row_stack_API_preserved=True,new_audition_or_C=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
