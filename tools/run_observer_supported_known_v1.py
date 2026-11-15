"""Known-first composite metric, exact bias and solver qualification; no media."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_complete_v1.fit import CompleteSystem
    from observer_inverse_v1.fit import real_vector,complex_array,RegularizedObserver
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem
    from observer_frequency_v1.optimality import bound
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem,SupportedBlockRight,infer_target
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    sources=('tools/run_observer_supported_known_v1.py','research/observer_supported_metric_v1_plan.json',
        'research/observer_supported_known_v1_plan.json','tools/observer_supported_v1/metric.py','tools/observer_supported_v1/fit.py',
        'tools/observer_complete_v1/frame.py','tools/observer_complete_v1/synthesis.py','tools/observer_complete_v1/fit.py',
        'tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py','tools/observer_inverse_v1/fit.py',
        'tools/observer_inverse_v1/regularizer.py','tools/observer_inverse_v1/refinement.py','tools/observer_frequency_v1/metric.py',
        'tools/observer_frequency_v1/fit.py','tools/observer_frequency_v1/optimality.py')
    r=dict(result='running',pid=os.getpid(),sources={},controls=[],cases=[],material_read=False)
    for n in sources:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
    print('SUPPORTED_KNOWN_PID',os.getpid(),flush=True)
    try:
        rng=np.random.default_rng(615146);N=4353;n=np.arange(N);positions=np.rint(np.linspace(0,N-1,9)).astype(int)
        orders=np.array([7,211]);root=64.;audio=rng.normal(size=(N,2));met=SupportedMetric(audio,root)
        test=rng.normal(size=met.shape)+1j*rng.normal(size=met.shape)
        lhs,rhs=np.vdot(met.forward(audio),test).real,np.vdot(audio,met.adjoint(test)).real
        adj=abs(lhs-rhs)/max(1.,abs(lhs));assert adj<2e-12
        original=met.weights.copy();met.weights[:]=2.5
        coverage_error=float(np.max(abs(met.adjoint(met.forward(audio))-6.25*met.time_coverage[:,None]*audio)))
        assert coverage_error<2e-11;met.weights[:]=original
        constant=SupportedMetric(np.ones((N,2)),root)
        assert abs(constant.band_power.sum()-1)<2e-12
        r['controls'].extend([dict(name='supported_adjoint',error=float(adj)),dict(name='uniform_actual_coverage',error=coverage_error),
            dict(name='constant_normalization',power=float(constant.band_power.sum()))])
        for label,rotation in (('swap',np.array([[0.,1.],[1.,0.]])),('rotation',np.array([[.6,.8],[-.8,.6]]))):
            other=SupportedMetric(audio@rotation,root)
            err=float(np.max(abs(other.weights/met.weights-1)));assert err<2e-12
            rowerr=float(np.max(abs(other.forward(audio@rotation)-met.forward(audio)@rotation)));assert rowerr<2e-12
            r['controls'].append(dict(name='shared_'+label,error=err,row_error=rowerr))
        scaled=SupportedMetric(audio*3.7,root)
        err=float(np.max(abs(scaled.forward(audio*3.7)-met.forward(audio))));assert err<2e-12
        assert abs(scaled.wave_scale/met.wave_scale-3.7)<2e-12
        r['controls'].append(dict(name='positive_scale',error=err))
        for label in ('first','last','between_HF','silent_right','zero'):
            wave=np.zeros_like(audio)
            if label=='first':wave[0]=[1.,-.2]
            elif label=='last':wave[-1]=[-.4,.7]
            elif label=='between_HF':wave[:,0]=np.cos(2*np.pi*211.37*n/1024);wave[:,1]=.4*np.cos(2*np.pi*212.61*n/1024+.3)
            elif label=='silent_right':wave[:,0]=audio[:,0]
            metric=SupportedMetric(wave,root);system=SupportedSystem(WaveSynthesis(N,positions,orders,2),np.ones((2,1)),metric)
            b=system.rhs(wave);rows=metric.forward(wave);back=metric.adjoint(rows)
            if label in ('first','last'):
                assert np.vdot(b[:system.wave_size],b[:system.wave_size]).real>0 and not np.any(rows)
            if label=='zero':assert not np.any(b) and np.array_equal(metric.weights,np.ones(2049))
            if label=='silent_right':assert not np.any(rows[:,:,1]) and not np.any(back[:,1])
            path=a.out/('control_'+label+'.npz')
            np.savez_compressed(path,audio=wave,weights=metric.weights,band_power=metric.band_power,rows=rows,normal=back,
                time_coverage=metric.time_coverage,rhs=b,wave_scale=metric.wave_scale)
            r['controls'].append(dict(name=label,file=path.name,sha256=sha(path)))
        np.savez_compressed(a.out/'metric_controls.npz',audio=audio,test=test,weights=met.weights,rows=met.forward(audio),
            gradient=met.adjoint(test),coverage=met.time_coverage,constant_power=constant.band_power)
        r['metric_controls_sha256']=sha(a.out/'metric_controls.npz')
        stereo=SupportedSystem(WaveSynthesis(N,positions,orders,2),np.array([[1.],[.01]]),met)
        u=rng.normal(size=stereo.nsize);v=rng.normal(size=stereo.shape[0])
        stereo_adjoint=float(abs(np.dot(stereo@u,v)-np.dot(u,stereo.rmatvec(v)))/max(1.,abs(np.dot(stereo@u,v))))
        assert stereo_adjoint<2e-11
        sr=SupportedBlockRight(stereo);p=rng.normal(size=stereo.nsize);g=rng.normal(size=stereo.nsize)
        assert abs(np.dot(sr.apply(p),g)-np.dot(p,sr.transpose(g)))<2e-9
        np.savez_compressed(a.out/'stereo_controls.npz',audio=audio,positions=positions,orders=orders,scale=stereo.scale,
            u=u,v=v,forward=stereo@u,backward=stereo.rmatvec(v),p=p,g=g,right_matrix=sr.matrix,
            right_forward=sr.apply(p),right_backward=sr.transpose(g))
        r['stereo_controls_sha256']=sha(a.out/'stereo_controls.npz');r['stereo_system_adjoint_error']=stereo_adjoint
        synthesis=WaveSynthesis(N,positions,orders,1)
        for weak in (1.,.01,.0001,.00001):
            scale=np.array([[1.],[weak]])
            for law in ('constant','curved'):
                label=f'{law}_{weak:g}';folder=a.out/label;folder.mkdir()
                q=np.ones(synthesis.shape,complex);q[:,0,0]=1.+.15j
                q[:,1,0]=(1.+.3j if law=='constant' else 1.+.8*np.cos(np.arange(9)*np.pi)+.3j*np.sin(np.arange(9)*.9))
                nodes=q*scale[None];audio=synthesis.synthesize(nodes);metric=SupportedMetric(audio,root)
                old=RegularizedObserver(synthesis.operator,scale);full=CompleteSystem(synthesis,scale,metric.wave_scale)
                allweighted=WeightedSystem(synthesis,scale,FrequencyMetric(audio,root));new=SupportedSystem(synthesis,scale,metric)
                values=dict(source_nodes=nodes,audio=audio,positions=positions,orders=orders,scale=scale,
                    weights=metric.weights,band_power=metric.band_power,floor_active=metric.floor_active,wave_scale=metric.wave_scale)
                case=dict(label=label,law=law,weak_amplitude=weak,variants={},metric_floor_active=metric.floor_active.tolist())
                def describe(fitted):
                    mask=np.array([0.,1.])[None,:,None];truth=synthesis.synthesize(nodes*mask);high=synthesis.synthesize(fitted*mask)
                    return dict(wave_NRMSE=float(np.linalg.norm(synthesis.synthesize(fitted)-audio)/np.linalg.norm(audio)),
                        high_component_NRMSE=float(np.linalg.norm(high-truth)/np.linalg.norm(truth)))
                for tag,system,target in (('old_harmonic',old,old.observer.forward(nodes)),('global_wave',full,audio),
                    ('weighted_frame',allweighted,audio),('supported',new,audio)):
                    A=np.column_stack([system@x for x in np.eye(system.nsize)]);b=system.rhs(target)
                    x,_,rank,singular=linalg.lstsq(A,b,lapack_driver='gelsd');assert rank==system.nsize
                    fitted=complex_array(x,synthesis.shape)*scale[None];residual=A@x-b
                    gradient=float(np.linalg.norm(A.T@residual)/max(np.linalg.norm(A.T@b),1e-24));assert gradient<2e-9
                    values.update({tag+'_nodes':fitted,tag+'_normal_matrix':A.T@A,tag+'_normal_rhs':A.T@b})
                    case['variants'][tag]=dict(**describe(fitted),objective=float(residual@residual),relative_stationarity=gradient,dense_condition=float(singular[0]/singular[-1]))
                    if tag=='supported':
                        right=SupportedBlockRight(system);P=np.column_stack([right.apply(t) for t in np.eye(system.nsize)])
                        assert np.linalg.svd(P,compute_uv=False).min()>0
                        case['preconditioned_dense_condition']=float(np.linalg.cond(A@P));values['right']=P;values['right_matrix']=right.matrix
                        certificate=bound(new,audio,fitted);case['dense_certificate']=certificate
                        assert certificate['additional_gap_gate_passed']
                fitted,info,right=infer_target(new,audio)
                exact=values['supported_nodes'];error=float(np.linalg.norm((fitted-exact)/scale[None])/np.linalg.norm(exact/scale[None]))
                certificate=bound(new,audio,fitted)
                case['variants']['iterative']=dict(**info,**describe(fitted),dense_relative_error=error)
                case['iterative_certificate']=certificate;values['iterative_nodes']=fitted
                case['fidelity_qualified']=case['variants']['supported']['high_component_NRMSE']<.02
                case['solver_qualified']=bool(info['converged'] and error<2e-7 and certificate['additional_gap_gate_passed'] and case['preconditioned_dense_condition']<1e6)
                path=folder/'capture.npz';np.savez_compressed(path,**values);case.update(file=label+'/capture.npz',sha256=sha(path))
                r['cases'].append(case);save(a.out/'report.json',r)
                print('SUPPORTED KNOWN',label,'high',case['variants']['supported']['high_component_NRMSE'],'cond',case['preconditioned_dense_condition'],
                    'fidelity',case['fidelity_qualified'],'solver',case['solver_qualified'],flush=True)
        r.update(result='observer_supported_known_measured',dense_cases=8,all_fidelity_qualified=all(c['fidelity_qualified'] for c in r['cases']),
            all_solver_qualified=all(c['solver_qualified'] for c in r['cases']),material_read=False)
        save(a.out/'report.json',r);print(r['result'],r['all_fidelity_qualified'],r['all_solver_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
