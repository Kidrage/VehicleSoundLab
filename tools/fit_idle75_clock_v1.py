"""Fit75only timing against source moments through frozen procedural OSC observations."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle75_clock_v1.row import prepare,nodes,gain,native,weights
from idle75_clock_v1.forward import cache,predict,moments,ensemble,fit
from idle_phase_recipe_v1.phase import spline,phasors
from idle_phase_amplitude_v1.model import interpolation,native as old_native,gains
from idle_phase_amplitude_v1.observe import observe

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},known={},streams=[],models={},CHECK=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)


try:
    names=['tools/fit_idle75_clock_v1.py','tools/idle75_clock_v1/row.py','tools/idle75_clock_v1/forward.py',
        'tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_amplitude_v1/model.py','tools/idle_phase_amplitude_v1/observe.py',
        'tools/research_archive_v1.py','research/idle75_clock_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    parent=a.workspace/'baselines';am=load(track(parent/'idle_phase_amplitude_v1/evidence/render2/model.json'))
    model=prepare(np.array(am['taps'])[:,0,:],am['node_rate']);table=interpolation(am)
    save(a.out/'row.json',{key:value.tolist() if isinstance(value,np.ndarray) else value for key,value in model.items()})
    w,dw=weights(np.arange(960)/960);C=model['covariance'];variance=np.einsum('ti,ij,tj->t',w,C,w)
    normalization=np.sqrt(model['variance']/variance)
    r['known']['all960_marginal_variance_error']=float(abs(normalization**2*variance-model['variance']).max())
    assert r['known']['all960_marginal_variance_error']<1e-12
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    freq=np.array(profile['modal']['frequencies_hz']);amplitude=load(track(parent/'idle_local_partition_v1/evidence/compile2/model.json'))['main_amplitude_LR'][0][0]
    phase_root=parent/'idle_phase_recipe_v1/evidence/render2';phase_model=load(track(phase_root/'model.json'))
    actual=parent/'idle_local_partition_v1/evidence/render1';renders=load(track(actual/'report.json'))
    streams=[];responses=[]
    for row in renders['renders']:
        seed=row['seed'];values,white=nodes(model,seed,12.)
        with np.load(track(actual/row['nodes_file'])) as f:old_values=f['nodes']
        x=old_native(old_values,table,0,144000);old_gain=gains(x,1.,table['covariance'])[:,0]
        mix_path=track(actual/row['files']['mix_1.0']['file']);mix,rate=sf.read(mix_path,always_2d=True);assert rate==48000
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(phase_model,f['coordinate_nodes'])
        z=phasors(phase_model,motion,np.arange(144000)/48000)
        response=cache(freq,z,mix[:144000,0],amplitude,old_gain)
        # Independent full-wave original observer validates the new cached path.
        g,jac,_=gain(model,values,144000,[1.,1.])
        wave=mix[:144000,0]+z[:,0].real*amplitude*(g-old_gain)
        coefficients=observe(np.column_stack((wave,wave)),freq,z)['coefficients'][:,1]
        error=float(abs(coefficients-predict(response,g)).max());assert error<1e-10
        derivative_error=[];central_errors=[]
        fraction=np.remainder(np.arange(144000)/48000*model['node_rate'],1.)
        for k in range(2):
            step=np.zeros(2);step[k]=1e-6
            plus=gain(model,values,144000,np.ones(2)+step)[0];minus=gain(model,values,144000,np.ones(2)-step)[0]
            central=(plus-minus)/(2e-6);central_errors.append(float(abs(central-jac[:,k]).max()))
            if k==0:
                plus2=gain(model,values,144000,np.ones(2)+2*step)[0];minus2=gain(model,values,144000,np.ones(2)-2*step)[0]
                forward=(-3*g+4*plus-plus2)/(2e-6);backward=(3*g-4*minus+minus2)/(2e-6)
                numerical=np.where(fraction<=.5,forward,backward)
            else:numerical=central
            derivative_error.append(float(abs(numerical-jac[:,k]).max()))
        assert max(derivative_error)<1e-6
        path=a.out/f'stream_{seed}.npz';np.savez_compressed(path,nodes=values,white=white,old_gain=old_gain,
            phasors=z,baseline_mix=mix[:144000,0],response_h=response['h'],response_constant=response['constant'])
        r['streams'].append(dict(seed=seed,file=path.name,sha256=sha(path),original_mix_file=str(mix_path),
            forward_error=error,native_derivative_errors=derivative_error,original_central_errors=central_errors));streams.append(values);responses.append(response)
    # Known conditional stream target, never a real latent-excitation claim.
    truth=np.array([1.4,1.15]);target,_=ensemble(model,streams,responses,truth)
    known=fit(model,streams,responses,target);r['known']['inverse']=known
    r['known']['truth']=truth.tolist();r['known']['parameter_error']=float(abs(np.array(known['parameters'])-truth).max())
    checkpoint();assert known['available'] and r['known']['parameter_error']<1e-5
    r['independent_control_moments']=ensemble(model,streams,responses,[1.,1.])[0].tolist()
    source=parent/'idle_variation_budget_v1/evidence/observe1';source_report=load(track(source/'report.json'))
    data={}
    for row in source_report['cases']:
        if row['metadata']['kind'] not in ['source','samePSD_control']:continue
        path=track(source/row['file']);assert sha(path)==row['sha256']
        with np.load(path) as f:data[row['label']]=f['covariance'][[25,27,30,35],0,0]
    for family in ['source','phase_149921','phase_277139','phase_381611']:
        r['models'][family]=fit(model,streams,responses,data[family+'_train']);checkpoint()
        print(dict(family=family,available=r['models'][family]['available'],parameters=r['models'][family]['parameters'],
            bounds=r['models'][family]['active_mask']),flush=True)
    for family,fit_model in r['models'].items():
        if not fit_model['available']:continue
        prediction=np.array(fit_model['TRAIN_prediction']);target=data[family+'_check']
        r['CHECK'].append(dict(family=family,target=target.tolist(),same3seed_predicted_moments=prediction.tolist(),
            scaled_error_with_TRAIN_variance=float(np.sum(((prediction-target)/data[family+'_train'][0])**2)),
            scope='Same generator training-ensemble prediction against already-inspected source CHECK, not new synthetic heldout audio'))
    r.update(result='idle75_clock_fitted_pending_audit',source_available=r['models']['source']['available'],
        fit_recording_samples_used_in_synthesis=False,latent_excitation_recovered=False,
        independent75_stream_and_missing_old_cross_coupling_explicit=True,new_audio_or_C=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],known_error=r['known'].get('parameter_error'),source=r['models'].get('source')),flush=True)
