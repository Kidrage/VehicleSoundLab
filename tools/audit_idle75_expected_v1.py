"""Independent operators and conditional Gaussian moment audit; never reruns a fit."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.sparse import load_npz
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),operators=[],expected_replays=[],trace_cost_checks=0)
plan=Path(__file__).resolve().parents[1]/'research/idle75_expected_v1_audit_plan.json'
shutil.copy2(plan,a.out/plan.name);r['plan_sha256']=sha(plan)


def interpolation(u):
    return np.column_stack((-.5*u*(1-u)**2,1+u*u*(1.5*u-2.5),u*(.5+u*(2-1.5*u)),.5*u*u*(u-1)))


def expected(model,times,operators,constants,parameter):
    # Direct signed-lag FIR autocovariance and all16 node pairs. No production imports.
    h=np.array(model['taps']);q=times*model['node_rate'];p=q*parameter[0];k=np.floor(p).astype(int);u=p-k
    w=interpolation(u)
    cov=np.array([np.einsum('ij,ij->',h[:len(h)-j],h[j:]) for j in range(len(h))])
    node=np.array([[cov[abs(i-j)] for j in range(4)] for i in range(4)])
    w*=np.sqrt(model['variance']/np.einsum('ti,ij,tj->t',w,node,w))[:,None]
    C=np.zeros((len(k),len(k)));pad=np.r_[cov,0.]
    for first in range(0,len(k),128):
        last=min(first+128,len(k))
        for i in range(4):
            for j in range(4):
                distance=np.minimum(abs((k[first:last]+i)[:,None]-(k+j)[None,:]),len(cov))
                C[first:last]+=np.outer(w[first:last,i],w[:,j])*pad[distance]
    s=parameter[1];G=np.exp(-s*s*model['variance'])*np.expm1(s*s*C);mean=np.exp(-.5*s*s*model['variance'])
    values=[];eigen=[]
    for B,constant in zip(operators,constants):
        # Center the observation operator, independently of the production K-centering.
        dense=B.toarray();mean_value=constant+mean*dense.sum(axis=1);mean_value-=mean_value.mean()
        dense-=dense.mean(axis=0,keepdims=True);K=(dense@G)@dense.T
        values.append([float((np.diag(K,lag).sum()+mean_value[:len(K)-lag]@mean_value[lag:])/(len(K)-lag)) for lag in [0,2,5,10]])
        eigen.append(float(np.linalg.eigvalsh(K).min()))
    return np.mean(values,axis=0),min(eigen)


try:
    run=load(a.input/'report.json')
    for path,digest in run['sources'].items():assert sha(a.input/'exact_sources'/path)==digest
    for path,digest in run['inputs'].items():assert sha(path)==digest
    frozen=a.workspace/'baselines/idle75_clock_v1/evidence/fit2';old=load(frozen/'report.json');model=load(frozen/'row.json')
    reference=load(a.workspace/'baselines/idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'][0][0]
    operators={1000:[],2000:[]};constants={1000:[],2000:[]};grids={}
    maximum_native=0.
    for index,row in enumerate(old['streams']):
        with np.load(frozen/row['file']) as f:h=f['response_h'];constant=f['response_constant'];nodes=f['nodes']
        for rate in operators:
            B=load_npz(a.input/f'operator_{row["seed"]}_{rate}.npz')
            with np.load(a.input/f'offset_{row["seed"]}_{rate}.npz') as f:offset=f['constant'];times=f['times']
            assert np.array_equal(offset,(constant/reference).real)
            assert np.array_equal(times,(np.arange(3*rate+3)-1)/rate)
            maximum=0.
            for j,first in enumerate(range(12000,122401,960)):
                position=(np.arange(first,first+9600)/48000)*rate;k=np.floor(position).astype(int)
                w=interpolation(position-k);values=np.zeros(B.shape[1])
                for component in range(4):np.add.at(values,k+component,w[:,component]*(h[j]/reference).real)
                maximum=max(maximum,float(abs(values-B.getrow(j).toarray().ravel()).max()))
            assert maximum<1e-12
            r['operators'].append(dict(seed=row['seed'],grid_rate=rate,all116rows_maximum_error=maximum))
            operators[rate].append(B);constants[rate].append(offset);grids[rate]=times
        # Independently apply native clock/gain to all four predeclared cases.
        for point_index,point in enumerate([[.5,.25],[1.,1.],[1.4,1.15],[4.,3.]]):
            with np.load(a.input/f'native_{index}_{index*4+point_index+1}.npz') as f:native=f['native'];compressed=f['compressed'];grid_gain=f['grid_gain']
            t=np.arange(144000)/48000;position=t*model['node_rate']*point[0];k=np.floor(position).astype(int);w=interpolation(position-k)
            v=np.einsum('ti,ij,tj->t',w,np.array(model['covariance']),w)
            x=np.sum(w*nodes[k[:,None]+np.arange(1,5)],axis=1)*np.sqrt(model['variance']/v)
            gain=np.exp(point[1]*x-point[1]**2*model['variance'])
            actual=[]
            for j,first in enumerate(range(12000,122401,960)):
                actual.append(((constant[j]+h[j]@gain[first:first+9600])/reference).real)
            error=float(abs(np.array(actual)-native).max());assert error<1e-11
            coarse=operators[1000][index]@grid_gain+constants[1000][index]
            assert abs(coarse-compressed).max()<1e-12
            maximum_native=max(maximum_native,error)
    r['all_native_prediction_replay_error']=maximum_native
    replays=[]
    # Replay every fixed coarse grid control, independent fine target and each terminal inverse.
    for row in run['controls'].get('grid_moments',[]):replays.append(('grid_coarse',1000,row['parameters'],row['moments_1000']))
    for label,result in run['known'].items():
        if label=='truth':continue
        replays.append(('known_'+label,1000,result['parameters'],result['prediction']))
    if 'independent_fine_grid' in run['known']:
        replays.append(('known_fine_target',2000,run['known']['truth'],run['known']['independent_fine_grid']['target']))
    for family,result in run['models'].items():replays.append((family,1000,result['parameters'],result['prediction']))
    cache={}
    for label,rate,parameters,target in replays:
        key=(rate,tuple(parameters))
        if key not in cache:cache[key]=expected(model,grids[rate],operators[rate],constants[rate],parameters)
        value,minimum=cache[key];error=float(abs(value-np.array(target)).max());assert error<1e-11 and minimum>-1e-12
        r['expected_replays'].append(dict(label=label,grid_rate=rate,parameters=parameters,moments=value.tolist(),
            maximum_moment_error=error,minimum_centered_covariance_eigenvalue=minimum))
        save(a.out/'report.json',r);print(dict(label=label,error=error),flush=True)
    for label,result in list(run['known'].items())+list(run['models'].items()):
        if label=='truth':continue
        target=np.array(result['target']);scale=target[0]
        for trace in result['trace']:
            value=np.array(trace['moments']);cost=np.sum(((value-target)/scale)**2)
            assert abs(cost-trace['squared_error'])<1e-12;r['trace_cost_checks']+=1
        last=next(t for t in reversed(result['trace']) if np.array_equal(t['parameters'],result['parameters']))
        singular=np.linalg.svd(np.array(last['jacobian'])/scale,compute_uv=False)
        assert abs(singular-np.array(result['singular_values'])).max()<1e-9
        if label in run['known']:
            error=float(abs(np.array(result['parameters'])-np.array(run['known']['truth'])).max())
            assert abs(error-result['maximum_parameter_error'])<1e-12
    for row in run['CHECK']:
        result=run['models'][row['family']];error=np.sum(((np.array(result['prediction'])-np.array(row['target']))/result['target'][0])**2)
        assert abs(error-row['scaled_squared_error'])<1e-12
    if 'same_grid' in run['known']:
        truth=np.array(run['known']['truth']);step=1e-6;derivative=[]
        for axis in range(2):
            delta=np.zeros(2);delta[axis]=step
            plus=expected(model,grids[1000],operators[1000],constants[1000],truth+delta)[0]
            minus=expected(model,grids[1000],operators[1000],constants[1000],truth-delta)[0]
            derivative.append((plus-minus)/(2*step))
        target=next(row for row in run['controls']['grid_moments'] if row['parameters']==truth.tolist())['jacobian_1000']
        error=float(abs(np.array(derivative).T-np.array(target)).max());assert error<1e-6
        r['independent_expected_Jacobian_error']=error
    r.update(result='conditional_expected75_operator_and_terminal_moments_independently_checked',
        all_stored_trace_costs_checked=True,trace_kernels_independently_replayed=False,no_optimization_run=True,
        source_models_fitted=len(run['models']),new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],replays=len(r['expected_replays']),traces=r['trace_cost_checks']),flush=True)
