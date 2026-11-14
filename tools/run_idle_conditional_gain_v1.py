"""Source conditional mean through native OSC projection, not a new voice or likelihood."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from idle_conditional_gain_v1.forward import prepare,response,waveform,gains
from idle_conditional_gain_v1.model import fit,metrics,uncertainty
from idle_phase_amplitude_v1.observe import observe

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-conditional-gain/1',result='running',sources={},inputs={},known={},models={},evaluations=[])
truth=np.array([[.02,.04,-.08,.10,.06],[-.03,-.06,.05,-.07,.09]]).ravel()


def checkpoint():save(a.out/'report.json',r)
def track(path):r['inputs'][str(path)]=sha(path);return path
def keep(name,**values):
    path=a.out/(name+'.npz');np.savez_compressed(path,**values)
    return dict(file=path.name,sha256=sha(path))
def beta_from_spec(spec):
    c=np.array(spec['amplitude'])*np.exp(1j*np.array(spec['initial']))
    return np.r_[c.real,-c.imag,0.]


try:
    names=['tools/run_idle_conditional_gain_v1.py','tools/idle_conditional_gain_v1/forward.py',
        'tools/idle_conditional_gain_v1/model.py','tools/joint_osc_forward_v1/projection.py',
        'tools/idle_phase_amplitude_v1/observe.py','tools/research_archive_v1.py','research/idle_conditional_gain_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    # Known procedural phases, NOT real amplitude innovations or recording tracks.
    prior=a.workspace/'baselines/joint_osc_forward_v1/evidence/run2'
    spec=load(track(prior/'spec.json'));beta=beta_from_spec(spec);freq=np.array(spec['frequencies'])
    with np.load(track(prior/'stream_149921.npz')) as f:z=f['phasors'][:144000]
    prepared=prepare(freq,z,beta);target=response(prepared,truth)
    x=waveform(prepared,truth);measured=observe(np.column_stack((x,x)),freq,z)['coefficients'][:,[1,2,4]]
    known_error=float(abs(target-measured).max());assert known_error<1e-10
    r['known']['forward_identity_error']=known_error
    r['known']['finite_difference_controls']=[]
    for point in [np.zeros(10),truth]:
        value,jac=response(prepared,point,True);cols=[]
        for k in range(10):
            step=np.zeros(10);step[k]=1e-6
            cols.append((response(prepared,point+step)-response(prepared,point-step))/(2e-6))
        error=float(abs(np.stack(cols,axis=-1)-jac).max());assert error<1e-7
        r['known']['finite_difference_controls'].append(dict(parameters=point.tolist(),maximum_error=error))
    const=fit(prepared,target);model=fit(prepared,target,const)
    r['known'].update(constant=const,conditional=model,truth=truth.tolist(),
        parameter_error=float(abs(np.array(model['parameters'])-truth).max()),
        amplitude_innovations_supplied=False,scope='Exact conditional mean only, no hidden variance inference')
    checkpoint()
    assert const['available'] and model['available'] and r['known']['parameter_error']<1e-5
    r['known']['training_arrays']=keep('known_train',frequencies=freq,phasors=z,beta=beta,
        center=prepared['center'],truth=truth,target=target,mean_audio=x,parameters=np.array(model['parameters']))
    center=prepared['center'].copy();del prepared
    r['known']['predictions']=[]
    for seed in [149921,277139,381611]:
        with np.load(track(prior/('stream_'+str(seed)+'.npz'))) as f:allz=f['phasors']
        for part,first in [('train',0),('check',144000)]:
            if seed==149921 and part=='train':continue
            z=allz[first:first+144000];q=prepare(freq,z,beta,center)
            target=response(q,truth);pred=response(q,model['parameters']);error=float(abs(pred-target).max());assert error<1e-7
            row=dict(seed=seed,part=part,maximum_coefficient_error=error,
                **keep(f'known_{seed}_{part}',frequencies=freq,phasors=z,beta=beta,center=center,
                    truth=truth,target=target,prediction=pred,mean_audio=waveform(q,model['parameters'])))
            r['known']['predictions'].append(row);del q
    # Unknown positive mean-one innovations can be marginalized for this mean;
    # they are not the real source innovations and their covariance is unidentified.
    gh,gw=np.polynomial.hermite.hermgauss(9);sigmas=np.array([.12,.10])
    marginal=np.sum(gw[:,None]/np.sqrt(np.pi)*np.exp(np.sqrt(2)*gh[:,None]*sigmas-.5*sigmas**2),axis=0)
    r['known']['hidden_innovation_marginal_mean']=marginal.tolist()
    assert abs(marginal-1).max()<1e-12
    parent=a.workspace/'baselines/idle_local_partition_v1/evidence/observe1'
    parent_report=load(track(parent/'report.json'))
    profile=load(track(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    freq=np.array(profile['modal']['frequencies_hz']);families=['source','phase_149921','phase_277139','phase_381611']
    rows={row['label']:row for row in parent_report['cases'] if row['metadata']['kind'] in ['source','samePSD_control']}
    assert len(rows)==8
    # All four TRAIN models saved before any CHECK fit/metric is computed.
    for family in families:
        label=family+'_train';row=rows[label];file=track(parent/row['file']);assert sha(file)==row['sha256']
        with np.load(file) as f:z=f['phasors'];beta=f['global_coefficients'][:,0];target=f['local_coefficients'][:,[1,2,4]]
        q=prepare(freq,z,beta);zero=response(q,np.zeros(10));identity=float(abs(zero-q['coefficients'][[1,2,4]]).max());assert identity<1e-10
        const=fit(q,target);conditional=fit(q,target,const) if const['available'] else dict(available=False,reason='constant fit unavailable')
        r['models'][family]=dict(constant=const,conditional=conditional,zero_gain_identity_error=identity,
            TRAIN_beta=beta.tolist(),source_file=str(file),source_sha256=sha(file))
        checkpoint();del q
        print(dict(stage='TRAIN',family=family,constant=const['available'],conditional=conditional['available'],
            condition=conditional.get('condition'),nfev=conditional.get('nfev')),flush=True)
    for family in families:
        model=r['models'][family]
        if not model['constant']['available'] or not model['conditional']['available']:continue
        for part in ['train','check']:
            label=family+'_'+part;row=rows[label];file=track(parent/row['file']);assert sha(file)==row['sha256']
            with np.load(file) as f:z=f['phasors'];target=f['local_coefficients'][:,[1,2,4]]
            # Use TRAIN global13 coefficients for BOTH portions, including fixed187.
            q=prepare(freq,z,np.array(model['TRAIN_beta']),model['conditional']['center'])
            predictions={key:response(q,model[key]['parameters']) for key in ['constant','conditional']}
            results={key:metrics(target,value) for key,value in predictions.items()}
            base=np.array(results['constant']['complex_MSE']);new=np.array(results['conditional']['complex_MSE'])
            curve=uncertainty(predictions['conditional']-target)
            error_target=predictions['conditional']-target
            row_out=dict(family=family,part=part,metrics=results,fractional_complex_MSE_reduction=(1-new/base).tolist(),
                **keep(label,frequencies=freq,phasors=z,beta=np.array(model['TRAIN_beta']),center=q['center'],target=target,
                    constant_prediction=predictions['constant'],conditional_prediction=predictions['conditional'],
                    constant_audio=waveform(q,model['constant']['parameters']),conditional_audio=waveform(q,model['conditional']['parameters']),
                    constant_gain=gains(model['constant']['parameters'],q['x']),conditional_gain=gains(model['conditional']['parameters'],q['x']),
                    error_covariance_signed_lags=curve))
            if part=='train':row_out['descriptive_uncertainty']=dict(real_imag_covariance=curve[25].tolist(),
                coefficient_error_mean_real=error_target.mean(axis=0).real.tolist(),coefficient_error_mean_imag=error_target.mean(axis=0).imag.tolist(),
                calibrated=False,hidden_innovation_covariance_identified=False,overlapping_windows_not_independent=True)
            r['evaluations'].append(row_out);checkpoint();del q
    r.update(result='native_conditional_mean_fitted_pending_audit',CHECK_previously_inspected=True,
        source_conditional_mean_available=r['models']['source']['conditional']['available'],
        hidden_amplitude_covariance_identified=False,source_joint_distribution_identified=False,
        new_source_voice_or_audition=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],CHECK=[(v['family'],v['fractional_complex_MSE_reduction']) for v in r['evaluations'] if v['part']=='check']),flush=True)
