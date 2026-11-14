"""Known procedural joint source, exact window response, inverse and power controls."""
import argparse,shutil,sys,os
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.optimize import least_squares
from research_archive_v1 import load,save,sha
from joint_osc_forward_v1.gaussian import known_taps,delayed_taps,covariance,interpolation,nodes,native
from joint_osc_forward_v1.osc import specification,gains,gain_matrix,carriers,waveform,SELECTED
from joint_osc_forward_v1.projection import compile_response,apply,derivative,measure,simple_windows
from joint_osc_forward_v1.moments import finite_power,at_times
from idle_conditioned_detail_v1.features import phases

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.joint-osc-forward/1',result='running',sources={},cases=[],streams=[],power=[],fit={})
spec=specification();truth=np.array([.65,-.55]);seeds=[149921,277139,381611]
table=None
def serial(value):return value.tolist() if isinstance(value,np.ndarray) else value
def checkpoint():save(a.out/'report.json',r)
def file_record(path):return dict(file=path.name,sha256=sha(path))
def observe_case(seed,kind,x,z,g,log,amap):
    values={'audio':x,'gain':g,'loggain':log,'amplitude_map':amap};parts=[]
    for part,first in [('train',0),('check',144000)]:
        if first>=len(x):continue
        audio=x[first:first+144000];known=z[first:first+144000]
        true=measure(audio,spec,known)
        measured=phases(audio,spec['frequencies'][SELECTED]);observed=measure(audio,spec,measured)
        mean,logmean=simple_windows(g[first:first+144000])
        std=np.std(np.log(abs(observed['coefficients'][:,SELECTED])),axis=0)
        p95=float(np.quantile(abs(np.angle(measured[12000:-12000]/known[12000:-12000])),.95))
        noAM=kind in ['constant','phase_only']
        gate=bool(std.max()<=.003 and p95<=.05) if noAM else None
        values.update({part+'_true_coefficients':true['coefficients'],part+'_measured_coefficients':observed['coefficients'],
            part+'_measured_phasors':measured,part+'_Hann_mean_gain':mean,part+'_exp_Hann_mean_loggain':logmean})
        target=abs(true['coefficients'][:,SELECTED]);amplitude=spec['amplitude'][SELECTED]
        if noAM:assert abs(target/amplitude-1).max()<1e-10
        parts.append(dict(part=part,measured_log_std=std.tolist(),phase_error_p95_rad=p95,
            no_AM_original_gate=gate,known_phase_noAM_amplitude_error=float(abs(target/amplitude-1).max()) if noAM else None,
            naive_Hann_gain_max_relative_error=float(abs(target/(amplitude*mean)-1).max()),
            naive_exp_Hann_log_max_relative_error=float(abs(target/(amplitude*logmean)-1).max())))
        theta=2*np.pi*np.arange(first,first+len(audio))[:,None]/48000*spec['frequencies']+spec['initial']
        power=finite_power(spec,table['covariance'] if kind!='constant' else np.zeros((5,5)),amap,theta,audio)
        key=str(seed)+'_'+kind+'_'+part
        values[part+'_expected_modal_second_moment']=power.pop('expected_modal_second_moment')
        for name in ['theoretical_first','theoretical_same','theoretical_opposite']:values[part+'_'+name]=power.pop(name)
        r['power'].append(dict(case=key,**power))
    path=a.out/(kind+'_'+str(seed)+'.npz');np.savez_compressed(path,**values)
    row=dict(seed=seed,kind=kind,frames=len(x),parts=parts,**file_record(path));r['cases'].append(row);checkpoint()
    print(dict(seed=seed,kind=kind,observed=[(q['part'],q['measured_log_std'],q['no_AM_original_gate']) for q in parts]),flush=True)
    return values

try:
    names=['tools/run_joint_osc_forward_v1.py','tools/joint_osc_forward_v1/gaussian.py','tools/joint_osc_forward_v1/osc.py',
        'tools/joint_osc_forward_v1/projection.py','tools/joint_osc_forward_v1/moments.py',
        'tools/idle_phase_amplitude_v1/observe.py','tools/idle_conditioned_detail_v1/features.py',
        'research/joint_osc_forward_v1_plan.json','tools/research_archive_v1.py']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    save(a.out/'spec.json',{key:serial(value) for key,value in spec.items()})
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        delayed=delayed_taps();c=covariance(delayed);dtable=interpolation(delayed)
        assert abs(c[2,0,1]-.14)<1e-14 and abs(c[2,1,0])<1e-14
        taps=known_taps();table=interpolation(taps)
        np.savez_compressed(a.out/'kernels.npz',taps=taps,delayed_taps=delayed,
            **{'main_'+key:value for key,value in table.items()},**{'delayed_'+key:value for key,value in dtable.items()})
        r['known_covariance']=dict(delayed_cross_error=float(abs(c[2,0,1]-.14)),
            delayed_full_fractional_error=dtable['error'],main_full_fractional_error=table['error'])
        # A deterministic zero-motion control is outside the stationary random cases.
        zero=np.zeros((144000,5));_,z,cosine,base=carriers(spec,zero)
        g,j,log,amap=gains(zero,np.zeros((5,5)),[0,0],spec,False)
        observe_case(0,'constant',waveform(spec,cosine,base,g),z,g,log,amap)
        for seed in seeds:
            value,white=nodes(taps,seed,6);latent=native(value,table,288000)
            deterministic,z,cosine,base=carriers(spec,latent)
            path=a.out/('stream_'+str(seed)+'.npz');np.savez_compressed(path,nodes=value,white=white,
                latent=latent,phasors=z,base=base)
            r['streams'].append(dict(seed=seed,seconds=6,**file_record(path)))
            for kind,parameters,enabled in [('phase_only',[0,0],False),('independent_AM',[0,0],True),('joint_AM',truth,True)]:
                g,j,log,amap=gains(latent,table['covariance'],parameters,spec,enabled)
                x=waveform(spec,cosine,base,g);observe_case(seed,kind,x,z,g,log,amap)
        # Fit the known two parameters with the entire latent input supplied.
        with np.load(a.out/'stream_149921.npz') as f:latent=f['latent'][:144000];z=f['phasors'][:144000];base=f['base'][:144000]
        with np.load(a.out/'joint_AM_149921.npz') as f:target=np.log(abs(f['train_true_coefficients'][:,SELECTED]))
        cache=compile_response(spec,z,z.real,base);r['forward_known_identity']=[]
        for kind,parameters,enabled in [('phase_only',[0,0],False),('independent_AM',[0,0],True),('joint_AM',truth,True)]:
            g,j,_,_=gains(latent,table['covariance'],parameters,spec,enabled);pred=apply(cache,g)
            with np.load(a.out/(kind+'_149921.npz')) as f:coefficient=f['train_true_coefficients'][:,SELECTED]
            error=float(abs(pred-coefficient).max());assert error<1e-10
            r['forward_known_identity'].append(dict(kind=kind,maximum_complex_coefficient_error=error))
        def response(parameters):
            g,j,_,_=gains(latent,table['covariance'],parameters,spec)
            coefficient=apply(cache,g);dc=derivative(cache,j)
            if np.any(abs(coefficient)<=0):raise ValueError('Undefined model log magnitude')
            prediction=np.log(abs(coefficient));jac=np.real(dc/coefficient[None,:,:])
            return prediction,np.moveaxis(jac,0,-1).reshape(-1,2)
        r['jacobian_controls']=[]
        for parameters in [np.array([0.,0.]),np.array([.25,-.15])]:
            prediction,jac=response(parameters);columns=[]
            for i in range(2):
                step=np.zeros(2);step[i]=1e-6
                columns.append(((response(parameters+step)[0]-response(parameters-step)[0])/(2e-6)).ravel())
            error=float(abs(jac-np.column_stack(columns)).max());assert error<1e-7
            r['jacobian_controls'].append(dict(parameters=parameters.tolist(),central_difference_error=error))
        trace=[]
        def fun(parameters):
            prediction,jac=response(parameters);residual=(prediction-target).ravel()
            trace.append(dict(parameters=parameters.tolist(),squared_error=float(residual@residual)))
            return residual
        result=least_squares(fun,[0.,0.],jac=lambda q:response(q)[1],bounds=(-.9,.9),
            max_nfev=40,xtol=1e-11,ftol=1e-11,gtol=1e-11)
        final,jac=response(result.x);singular=np.linalg.svd(jac,compute_uv=False)
        assert result.success and np.max(abs(result.x-truth))<1e-6 and np.all(abs(result.x)<.9-1e-6)
        assert singular[-1]>0 and singular[0]/singular[-1]<=1000
        r['fit']=dict(parameters=result.x.tolist(),truth=truth.tolist(),maximum_parameter_error=float(abs(result.x-truth).max()),
            nfev=result.nfev,njev=result.njev,status=result.status,success=bool(result.success),
            Jacobian_singular_values=singular.tolist(),Jacobian_condition=float(singular[0]/singular[-1]),
            training_maximum_log_error=float(abs(final-target).max()),trace=trace,
            known_latent_inputs_supplied=True,real_engine_hidden_excitation_recovered=False)
        del cache
        r['predictions']=[]
        for seed in seeds:
            with np.load(a.out/('stream_'+str(seed)+'.npz')) as f:latent=f['latent'];z=f['phasors'];base=f['base']
            g,_,_,_=gains(latent,table['covariance'],result.x,spec);x=waveform(spec,z.real,base,g)
            with np.load(a.out/('joint_AM_'+str(seed)+'.npz')) as f:actual=f['audio'];expected=[f['train_true_coefficients'],f['check_true_coefficients']]
            waveerror=float(abs(x-actual).max());assert waveerror<1e-7
            for k,part in enumerate(['train','check']):
                pred=measure(x[k*144000:(k+1)*144000],spec,z[k*144000:(k+1)*144000])['coefficients']
                error=float(abs(np.log(abs(pred[:,SELECTED]))-np.log(abs(expected[k][:,SELECTED]))).max());assert error<1e-6
                r['predictions'].append(dict(seed=seed,part=part,maximum_native_wave_error=waveerror,maximum_window_log_error=error,
                    used_for_fit=bool(seed==149921 and part=='train')))
        # Seed-independent Gaussian expectation, separately checked by numerical quadrature.
        from itertools import product
        gh,weights=np.polynomial.hermite.hermgauss(9);indices=np.array(list(product(range(9),repeat=5)))
        standard=np.sqrt(2)*gh[indices];probability=np.prod(weights[indices]/np.sqrt(np.pi),axis=1)
        qlatent=standard@np.linalg.cholesky(table['covariance']).T
        times=np.array([.35,1.11,2.65,3.35,5.65]);theta=2*np.pi*times[:,None]*spec['frequencies']+spec['initial']
        r['quadrature']=[]
        for kind,parameters,enabled in [('phase_only',[0,0],False),('independent_AM',[0,0],True),('joint_AM',truth,True)]:
            g,_,_,amap=gains(qlatent,table['covariance'],parameters,spec,enabled)
            theoretical_mean,theoretical_second=at_times(spec,table['covariance'],amap,theta)
            empirical=[]
            for angle in theta:
                real=np.cos(angle+qlatent@spec['phase_map'].T)
                amplitude=np.tile(spec['amplitude'],(len(real),1));amplitude[:,SELECTED]*=g
                x=np.sum(real*amplitude,axis=1);empirical.append([probability@x,probability@(x*x)])
            error=float(abs(np.array(empirical)-np.column_stack((theoretical_mean,theoretical_second))).max());assert error<1e-11
            r['quadrature'].append(dict(kind=kind,nodes_per_axis=9,total_nodes=len(probability),times=times.tolist(),
                maximum_first_second_moment_error=error,analytic_mean=theoretical_mean.tolist(),analytic_second=theoretical_second.tolist()))
        r['measured_no_AM_gates_passed']=all(part['no_AM_original_gate'] for row in r['cases'] if row['kind'] in ['constant','phase_only'] for part in row['parts'])
        r.update(result='known_joint_forward_inverse_and_moments_pending_audit',diagnostic_fixture_audio_only=True,
            new_source_voice_or_audition=False,source_model_fitted=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],fit=r['fit'],measured_noAM_gates=r.get('measured_no_AM_gates_passed')),flush=True)
