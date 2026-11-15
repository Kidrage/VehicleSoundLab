"""Additional genuine synthetic context around the identical original8 target windows."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original','original-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_inverse_v1.fit import real_vector,complex_array
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem,SupportedBlockRight,infer_target
    from observer_frequency_v1.optimality import bound
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},material_read=False)
    try:
        original,audit=load(a.original/'report.json'),load(a.original_audit/'report.json')
        assert original['result']=='observer_supported_known_measured' and not original['all_fidelity_qualified']
        assert audit['result']=='independent_observer_supported_known_passed' and audit['producer_sha256']==sha(a.original/'report.json')
        assert audit['auditor_sha256']==sha(repo/'tools/audit_observer_supported_known_v1.py')
        for n,d in original['sources'].items():assert sha(repo/n)==d
        names=tuple(original['sources'])+('tools/run_observer_context_known_v1.py','research/observer_context_known_v1_plan.json')
        for n in names:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
        for path in (a.original/'report.json',a.original_audit/'report.json'):r['inputs'][str(path)]=sha(path)
        print('CONTEXT_KNOWN_PID',os.getpid(),flush=True)
        for case in original['cases']:
            path=a.original/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as z:
                target=z['audio'];orders=z['orders'];scale=z['scale'];target_nodes=z['source_nodes'];old_fit=z['supported_nodes']
                step=int(z['positions'][1]-z['positions'][0]);assert np.all(np.diff(z['positions'])==step)
                padding=int(np.ceil(2048/step));offset=padding*step
                positions=np.arange(len(z['positions'])+2*padding)*step
                N=int(positions[-1]+1);indices=np.arange(-padding,len(z['positions'])+padding)
            source=np.ones((len(positions),2,1),complex);source[:,0,0]=1.+.15j
            source[:,1,0]=(1.+.3j if case['law']=='constant' else 1.+.8*np.cos(indices*np.pi)+.3j*np.sin(indices*.9))
            rotation=np.exp(-2j*np.pi*((orders*offset)%1024)/1024)
            source*=scale[None]*rotation[None,:,None]
            synth=WaveSynthesis(N,positions,orders,1);audio=synth.synthesize(source)
            mask=np.array([0.,1.])[None,:,None];high_truth=synth.synthesize(source*mask)
            target_synth=WaveSynthesis(len(target),np.arange(9)*step,orders,1)
            original_high=target_synth.synthesize(target_nodes*mask);crop=slice(offset,offset+len(target))
            assert np.max(abs(audio[crop]-target))<2e-12
            assert np.linalg.norm(high_truth[crop]-original_high)/np.linalg.norm(original_high)<2e-10
            metric=SupportedMetric(audio,64.);system=SupportedSystem(synth,scale,metric)
            A=np.column_stack([system@x for x in np.eye(system.nsize)]);b=system.rhs(audio)
            x,_,rank,singular=linalg.lstsq(A,b,lapack_driver='gelsd');assert rank==system.nsize
            fitted=complex_array(x,synth.shape)*scale[None];right=SupportedBlockRight(system)
            P=np.column_stack([right.apply(t) for t in np.eye(system.nsize)]);condition=float(np.linalg.cond(A@P))
            def describe(nodes):
                wave=synth.synthesize(nodes);high=synth.synthesize(nodes*mask)
                return dict(whole_wave_NRMSE=float(np.linalg.norm(wave-audio)/np.linalg.norm(audio)),
                    whole_high_NRMSE=float(np.linalg.norm(high-high_truth)/np.linalg.norm(high_truth)),
                    target_wave_NRMSE=float(np.linalg.norm(wave[crop]-target)/np.linalg.norm(target)),
                    target_high_NRMSE=float(np.linalg.norm(high[crop]-original_high)/np.linalg.norm(original_high)),
                    whole_high_region_NRMSE=[float(np.linalg.norm((high-high_truth)[s])/np.linalg.norm(high_truth[s])) for s in (slice(0,step),slice(step,-step),slice(-step,None))])
            dense_metrics=describe(fitted);dense_certificate=bound(system,audio,fitted)
            iterative,info,right=infer_target(system,audio);iterative_metrics=describe(iterative)
            error=float(np.linalg.norm((iterative-fitted)/scale[None])/np.linalg.norm(fitted/scale[None]))
            iterative_certificate=bound(system,audio,iterative)
            fidelity=dense_metrics['target_high_NRMSE']<.02
            solver=bool(info['converged'] and error<2e-7 and condition<1e6 and dense_certificate['additional_gap_gate_passed'] and iterative_certificate['additional_gap_gate_passed'])
            dest=a.out/(case['label']+'.npz')
            np.savez_compressed(dest,audio=audio,source_nodes=source,positions=positions,orders=orders,scale=scale,
                target_audio=target,target_source_nodes=target_nodes,no_context_nodes=old_fit,rotation=rotation,
                dense_nodes=fitted,iterative_nodes=iterative,right_matrix=right.matrix,right=P,weights=metric.weights,
                band_power=metric.band_power,floor_active=metric.floor_active,normal_matrix=A.T@A,normal_rhs=A.T@b)
            row=dict(label=case['label'],law=case['law'],weak_amplitude=case['weak_amplitude'],offset=offset,padding_nodes=padding,
                frames=N,target_frames=len(target),node_step=step,file=dest.name,sha256=sha(dest),
                no_context_target_high_NRMSE=case['variants']['supported']['high_component_NRMSE'],
                dense_metrics=dense_metrics,dense_certificate=dense_certificate,iterative_metrics=iterative_metrics,
                iterative_solve=info,iterative_dense_relative_error=error,iterative_certificate=iterative_certificate,
                preconditioned_dense_condition=condition,target_fidelity_qualified=fidelity,solver_qualified=solver,
                full_context_not_reclassified_as_pass=True)
            r['cases'].append(row);save(a.out/'report.json',r)
            print('CONTEXT KNOWN',case['label'],'target',dense_metrics['target_high_NRMSE'],'whole',dense_metrics['whole_high_NRMSE'],fidelity,solver,flush=True)
        r.update(result='observer_context_known_measured',all_target_fidelity_qualified=all(c['target_fidelity_qualified'] for c in r['cases']),
            all_solver_qualified=all(c['solver_qualified'] for c in r['cases']),source_fitted=False)
        save(a.out/'report.json',r);print(r['result'],r['all_target_fidelity_qualified'],r['all_solver_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
