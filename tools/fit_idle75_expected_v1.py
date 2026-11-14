"""Qualify conditional expected75gain statistics before fitting approved F2 moments."""
import argparse,gc,os,shutil,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import scipy
from research_archive_v1 import load,save,sha
from idle75_clock_v1.row import gain
from idle75_clock_v1.forward import predict
from idle75_expected_v1.kernel import features
from idle75_expected_v1.observer import compile,Expected
from idle75_expected_v1.inverse import fit
from idle75_expected_v1.controls import qualify

POINTS=[[.5,.25],[1.,1.],[1.4,1.15],[4.,3.]]
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},controls={},known={},models={},CHECK=[],
    libraries=dict(numpy=np.__version__,scipy=scipy.__version__),conditioning='Only independent75gain marginalized; frozen phases/detail conditioned')


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)
def progress(stage,**values):checkpoint();print(dict(stage=stage,**values),flush=True)


try:
    names=['tools/fit_idle75_expected_v1.py','tools/idle75_expected_v1/kernel.py','tools/idle75_expected_v1/observer.py',
        'tools/idle75_expected_v1/inverse.py','tools/idle75_expected_v1/controls.py','tools/idle75_clock_v1/row.py',
        'tools/idle75_clock_v1/forward.py','tools/research_archive_v1.py','research/idle75_expected_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    root=a.workspace/'baselines';frozen=root/'idle75_clock_v1/evidence/fit2';previous=load(track(frozen/'report.json'))
    model=load(track(frozen/'row.json'));model['taps']=np.array(model['taps']);model['covariance']=np.array(model['covariance'])
    reference=load(track(root/'idle_local_partition_v1/evidence/compile2/model.json'))['main_amplitude_LR'][0][0]
    r['controls']['finite_white_and_quadrature']=qualify(model,POINTS);progress('finite_white_and_quadrature_pass')
    streams=[];coarse=[];fine=[]
    for row in previous['streams']:
        file=track(frozen/row['file']);assert sha(file)==row['sha256']
        with np.load(file) as f:stream={key:f[key] for key in ['nodes','response_h','response_constant']}
        streams.append(stream)
        coarse.append(compile(stream['response_h'],stream['response_constant'],reference,1000))
        fine.append(compile(stream['response_h'],stream['response_constant'],reference,2000))
        for rate,c in [(1000,coarse[-1]),(2000,fine[-1])]:
            from scipy.sparse import save_npz
            save_npz(a.out/f'operator_{row["seed"]}_{rate}.npz',c['operator'])
            np.savez_compressed(a.out/f'offset_{row["seed"]}_{rate}.npz',constant=c['constant'],times=c['times'])
    native_controls=[]
    for index,(stream,c) in enumerate(zip(streams,coarse)):
        for point in POINTS:
            g=gain(model,stream['nodes'],144000,point)[0]
            k,w,_=features(model,c['times'],point[0]);x=np.sum(w*stream['nodes'][k[:,None]+np.arange(1,5)],axis=1)
            grid=np.exp(point[1]*x-point[1]**2*model['variance'])
            native=(predict(dict(h=stream['response_h'],constant=stream['response_constant']),g)/reference).real
            compressed=c['constant']+c['operator']@grid;error=float(abs(native-compressed).max())
            native_controls.append(dict(context=index,parameters=point,maximum_normalized_coefficient_error=error))
            np.savez_compressed(a.out/f'native_{index}_{len(native_controls)}.npz',native=native,compressed=compressed,grid_gain=grid)
            r['controls']['native_coefficients']=native_controls;checkpoint();assert error<=1e-5
    progress('all_native_gain_compression_pass',maximum_error=max(x['maximum_normalized_coefficient_error'] for x in native_controls))
    low=Expected(model,coarse);high=Expected(model,fine);grid_controls=[]
    for point in POINTS:
        start=time.perf_counter();v,j,m=low(point);v2,j2,m2=high(point)
        error=float(abs(v-v2).max()/v2[0]);row=dict(parameters=point,moments_1000=v.tolist(),moments_2000=v2.tolist(),
            jacobian_1000=j.tolist(),jacobian_2000=j2.tolist(),maximum_relative_moment_error=error,
            minimum_centered_covariance_eigenvalues=[m,m2],seconds=time.perf_counter()-start)
        grid_controls.append(row);r['controls']['grid_moments']=grid_controls;progress('grid_comparison',**row)
        assert error<=1e-4 and min(m,m2)>-1e-12
        gc.collect()
    truth=np.array([1.4,1.15]);r['known']['truth']=truth.tolist()
    for label,observer in [('same_grid',low),('independent_fine_grid',high)]:
        target=observer(truth)[0];result=fit(low,target);r['known'][label]=result
        error=float(abs(np.array(result['parameters'])-truth).max());result['maximum_parameter_error']=error
        progress('known_inverse',label=label,error=error,parameters=result['parameters'],available=result['available'])
        assert result['available'] and error<1e-5
    source=root/'idle_variation_budget_v1/evidence/observe1';source_report=load(track(source/'report.json'));data={}
    for row in source_report['cases']:
        if row['metadata']['kind'] not in ['source','samePSD_control']:continue
        file=track(source/row['file']);assert sha(file)==row['sha256']
        with np.load(file) as f:data[row['label']]=f['covariance'][[25,27,30,35],0,0]
    for family in ['source','phase_149921','phase_277139','phase_381611']:
        r['models'][family]=fit(low,data[family+'_train'])
        progress('source_or_control_fit',family=family,parameters=r['models'][family]['parameters'],available=r['models'][family]['available'])
    for family,result in r['models'].items():
        prediction=np.array(result['prediction']);target=data[family+'_check']
        r['CHECK'].append(dict(family=family,target=target.tolist(),prediction=prediction.tolist(),
            scaled_squared_error=float(np.sum(((prediction-target)/data[family+'_train'][0])**2)),
            scope='Already-inspected same-take CHECK; same conditional expected generator, NOT phase-estimator ensemble or new heldout audio'))
    r.update(result='conditional_expected75_moments_fitted_pending_audit',source_available=r['models']['source']['available'],
        expected_kernel_calls=low.calls+high.calls,new_audio_or_C=False,latent_excitation_recovered=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],known=r['known'],source=r['models'].get('source')),flush=True)
