"""Independent archive input/source bindings and all18 correction objectives."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','archive','repo','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path[:0]=[str(a.repo/'tools'),str(a.workspace/'tools/python_deps')]
    import numpy as np
    from observer_forward_v1.batched import BatchedObserver
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',checkpoints=0,input_bindings=0,historical_source_bindings=0,
        maximum_objective_relative_difference=0.,maximum_stationarity_absolute_difference=0.)
    try:
        manifest=load(a.archive/'manifest.json');entries={v['path']:v for v in manifest['files']}
        validation=load(a.archive/'validation.json');e=a.archive/'evidence'
        locations=validation['original_input_archive_locations']
        for name in ('tools/observer_forward_v1/batched.py','tools/observer_forward_v1/polyphase.py','tools/observer_forward_v1/operator.py'):
            assert sha(a.repo/name)==entries['source/'+name]['sha256']
        for folder in ('known1','precondition_known1','batched_known1','refinement_known1','real1','real2','real3','visibility1','visibility2'):
            record=load(e/folder/'report.json')
            for name,digest in record.get('sources',{}).items():
                path=e/folder/'exact_sources'/name
                assert sha(path)==digest==entries[path.relative_to(a.archive).as_posix()]['sha256']
                r['historical_source_bindings']+=1
            for name,digest in record.get('inputs',{}).items():
                path=a.archive/locations[name]
                assert sha(path)==digest==entries[locations[name]]['sha256']
                r['input_bindings']+=1
        for case in load(e/'real3/report.json')['cases']:
            folder=e/'real3'/case['label']
            with np.load(folder/'source.npz') as z:positions,target,frames=z['positions'],z['coefficients'],len(z['audio'])
            with np.load(folder/'scale.npz') as z:scale=z['scale']
            with np.load(e/'real2'/case['label']/'inverse.npz') as z:previous=z['nodes']
            op=BatchedObserver(frames,positions,np.arange(1,289),np.arange(1,289))
            D=np.zeros((len(positions)-2,len(positions)))
            for j in range(len(D)):
                left,right=np.diff(positions[j:j+3]);factor=2*256**2/(left+right)
                D[j,j:j+3]=[factor/left,-factor/left-factor/right,factor/right]
            initial=op.adjoint(target/scale[None]**2)*scale[None]
            def measure(nodes):
                q=nodes/scale[None];observed=op.forward(nodes)
                residual=(observed-target)/scale[None]
                d=(D@q.reshape(len(q),-1)).reshape((len(D),)+q.shape[1:])
                penalty=(D.T@d.reshape(len(D),-1)).reshape(q.shape)
                value=float(np.vdot(residual,residual).real+.001*np.vdot(d,d).real+.000001*np.vdot(q,q).real)
                gradient=op.adjoint((observed-target)/scale[None]**2)*scale[None]+.001*penalty+.000001*q
                stationarity=float(np.linalg.norm(gradient)/max(np.linalg.norm(initial),1e-24))
                return value,stationarity
            objective0,stationarity0=measure(previous)
            assert len(case['correction_stages'])==3
            for stage in case['correction_stages']:
                path=folder/stage['file'];assert sha(path)==stage['sha256']==entries[path.relative_to(a.archive).as_posix()]['sha256']
                with np.load(path) as z:nodes=z['nodes']
                objective,stationarity=measure(nodes)
                for value,expected in ((objective,stage['objective']),(objective0,stage['initial_objective'])):
                    error=abs(value-expected)/max(abs(value),1e-24);assert error<2e-8
                    r['maximum_objective_relative_difference']=max(r['maximum_objective_relative_difference'],error)
                for value,expected in ((stationarity,stage['relative_stationarity']),(stationarity0,stage['initial_relative_stationarity'])):
                    error=abs(value-expected);assert error<2e-9
                    r['maximum_stationarity_absolute_difference']=max(r['maximum_stationarity_absolute_difference'],error)
                assert objective<=objective0*(1+2e-10)
                assert stage['converged']==bool(stage['stop'] in (1,2,4,5) and stationarity<2e-7)
                previous=nodes;objective0,stationarity0=objective,stationarity;r['checkpoints']+=1
            with np.load(folder/'inverse.npz') as z:assert np.array_equal(previous,z['nodes'])
            assert case['cumulative_iterations']==case['parent_solve']['iterations']+sum(s['iterations'] for s in case['correction_stages'])
            print('AUDITED archived checkpoints',case['label'],flush=True)
        assert r['checkpoints']==18
        r.update(result='independent_inverse_archive_checkpoints_and_bindings_verified',
            manifest_sha256=sha(a.archive/'manifest.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
